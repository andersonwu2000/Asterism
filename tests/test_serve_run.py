"""GET /api/run contract tests — the mission-control read.

Same charter as test_serve_api: tmp workspace, no toolchain spawn,
read surface never writes. Worker lanes are engine-liveness claims
(live pid gate), file tails come from the real lean path (spawn writes
go through to real), and the idle console keeps telling the last run's
story via last_exit.scope.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.serve.app import create_app
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _no_network_quota(monkeypatch):
    """Tests never touch api.anthropic.com: default the quota fetch to
    'offline' and reset the memo around every test."""
    from Tooling.serve import run as _run

    def offline():
        raise OSError("no network in tests")
    monkeypatch.setattr(_run, "_fetch_oauth_usage", offline)
    _run._quota_memo.update(at=0.0, value=None, ttl=0.0, last_good=None)
    yield
    _run._quota_memo.update(at=0.0, value=None, ttl=0.0, last_good=None)


def _open_db(workspace: Path) -> sqlite3.Connection:
    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)
    return conn


def _client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _add_problem(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)",
        (name, db.now()))
    conn.commit()


def _fake_daemon(monkeypatch, *, running: bool = True, pid: int = 4321,
                 scope: "str | None" = None,
                 last_exit: "dict | None" = None) -> None:
    import Tooling.core.cli as _cli

    def fake_status(workspace):  # noqa: ANN001
        return {"running": running, "pid": pid if running else None,
                "scope": scope if running else None,
                "started_at": db.now() if running else None,
                "stopping": False, "in_flight_leases": 0,
                "last_exit": last_exit}
    monkeypatch.setattr(_cli, "daemon_status", fake_status)
    # this helper stands in for "the engine's state is now X"; in the
    # product every such transition goes through a chokepoint that
    # clears the serve-side reading, so the stand-in does too
    from Tooling.serve import daemon_cache as _daemon_cache
    _daemon_cache.invalidate()


def test_run_fresh_workspace_is_quiet(workspace: Path) -> None:
    r = _client(workspace).get("/api/run")
    assert r.status_code == 200
    body = r.json()
    assert body["workers"] == []
    assert body["goals"] is None
    # quota is garnish: offline → null, never an error
    assert body["quota"] is None


def test_run_shows_the_promotion_gate_builds(workspace: Path) -> None:
    """A promotion cold build is a machine-occupying job that no pipeline
    row describes — the console said "nobody on the field" through a
    10-minute one (owner, 2026-09-01). It rides the daemon block of the
    run payload, beside `in_flight` (human_interface_design.md §3.4)."""
    (workspace / ".asterism").mkdir()
    (workspace / ".asterism" / "promotion_gate.json").write_text(
        '{"builds": [{"strategy_id": 7,'
        ' "modules": ["Problems.p.proofs.L_a"],'
        ' "started_at": "2026-09-01T10:00:00+00:00"}]}', encoding="utf-8")
    body = _client(workspace).get("/api/run").json()
    assert [b["strategy_id"] for b in body["daemon"]["promotion_builds"]] == [7]


def test_run_quota_reads_the_oauth_windows(workspace: Path,
                                           monkeypatch) -> None:
    """The subscription meter: five_hour/seven_day utilization + the
    per-model scoped weekly limits, token never echoed."""
    from Tooling.serve import run as _run
    _run._quota_memo.update(at=0.0, value=None, ttl=0.0)
    canned = {
        "five_hour": {"utilization": 27.0,
                      "resets_at": "2026-07-07T06:59:59+00:00"},
        "seven_day": {"utilization": 31.0,
                      "resets_at": "2026-07-12T23:59:59+00:00"},
        "limits": [
            {"kind": "session", "percent": 27, "scope": None,
             "is_active": False},
            {"kind": "weekly_scoped", "percent": 60,
             "resets_at": "2026-07-12T23:59:59+00:00",
             "scope": {"model": {"display_name": "Fable"}},
             "is_active": True},
        ],
    }
    monkeypatch.setattr(_run, "_fetch_oauth_usage", lambda: canned)
    body = _client(workspace).get("/api/run").json()
    q = body["quota"]
    assert q["five_hour"]["utilization"] == 27.0
    assert q["seven_day"]["utilization"] == 31.0
    assert q["scoped"] == [{"name": "Fable", "percent": 60.0,
                            "resets_at": "2026-07-12T23:59:59+00:00",
                            "is_active": True}]
    assert "token" not in str(q).lower()

    # stale-while-error: a later blip serves the last good reading
    from Tooling.serve import run as _run2
    _run2._quota_memo.update(at=0.0, ttl=0.0)

    def blip():
        raise OSError("429")
    monkeypatch.setattr(_run2, "_fetch_oauth_usage", blip)
    again = _client(workspace).get("/api/run").json()["quota"]
    assert again["five_hour"]["utilization"] == 27.0


def test_run_live_lanes_carry_statement_and_file_tail(
        workspace: Path, monkeypatch) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="lemma_a",
                         lean_path="Problems/p/proofs/L_lemma_a.lean",
                         statement="a = a", origin="root")
    # a live lease owned by the daemon pid + one residue lease from a
    # dead pid — only the live one becomes a lane
    db.enqueue(conn, kind="Builder", target_id=str(gid),
               target_kind="Goal", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE target_id = ?", (db.now(), str(gid)))
    db.enqueue(conn, kind="Builder", target_id="999",
               target_kind="Goal", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 111, leased_at = ?"
                 " WHERE target_id = '999'", (db.now(),))
    conn.commit()
    conn.close()
    proof = workspace / "Problems" / "p" / "proofs" / "L_lemma_a.lean"
    proof.parent.mkdir(parents=True)
    proof.write_text("import Mathlib\n\ntheorem lemma_a : a = a := by\n  rfl\n",
                     encoding="utf-8")

    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    assert body["problem"] == "p"
    assert body["goals"]["total"] == 1
    assert len(body["workers"]) == 1
    lane = body["workers"][0]
    assert lane["kind"] == "Builder"
    assert lane["slug"] == "lemma_a"
    # the lane statement is the DISPLAY signature read from the stub
    # (binders included — goals.statement stores the bare conclusion;
    # context.goal_display_signature via serve, 2026-07-18)
    assert lane["statement"] == "theorem lemma_a : a = a"
    assert lane["file"] is not None
    assert "rfl" in lane["file"]["tail"]
    # the card shows the mathematics: prelude stripped
    assert "import" not in lane["file"]["tail"]
    assert lane["file"]["quiet_sec"] >= 0
    assert body["burn_run"] is not None
    assert body["burn_5h"] is not None


def test_run_lane_names_the_pipeline_it_is_running(
        workspace: Path, monkeypatch) -> None:
    """A lane is built from the queue LEASE, which holds no pipeline
    column — so the console's Signal sheet (`human_commands` kind
    Signal, §3.7) had nothing to aim at. The lane joins to its running
    `pipelines` row by the identity the dispatcher's own `running` set
    uses, (kind, target); a lane with no running row carries null
    rather than a neighbour's id, and a FINISHED row is not a worker.
    """
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    live = db.insert_goal(conn, problem="p", slug="lemma_a",
                          lean_path="Problems/p/proofs/L_lemma_a.lean",
                          statement="a = a", origin="root")
    done = db.insert_goal(conn, problem="p", slug="lemma_b",
                          lean_path="Problems/p/proofs/L_lemma_b.lean",
                          statement="b = b", origin="root")
    for gid in (live, done):
        db.enqueue(conn, kind="Builder", target_id=str(gid),
                   target_kind="Goal", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?",
                 (db.now(),))
    db.record_pipeline_start(conn, pipeline_id="pipe-live", kind="Builder",
                             target_id=str(live), target_kind="Goal")
    # same target, WRONG kind — a Verify row must not claim the Builder
    db.record_pipeline_start(conn, pipeline_id="pipe-verify", kind="Verify",
                             target_id=str(live), target_kind="Goal")
    # the other lane's only row is finished: no worker, no id
    db.record_pipeline_start(conn, pipeline_id="pipe-done", kind="Builder",
                             target_id=str(done), target_kind="Goal")
    db.finish_pipeline(conn, pipeline_id="pipe-done", status="succeeded",
                       outcome="proved")
    conn.commit()
    conn.close()

    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    lanes = {lane["slug"]: lane for lane in body["workers"]}
    assert lanes["lemma_a"]["pipeline_id"] == "pipe-live"
    assert lanes["lemma_b"]["pipeline_id"] is None


def test_run_forward_lane_tails_the_scratch_draft(
        workspace: Path, monkeypatch) -> None:
    """A Forward worker has no goal row and no landed file — its lane
    used to look forever idle while the LSP was hard at work. The lane
    now tails the freshest draft in the workarea whose Context.md
    title matches (kind, problem); probe helpers (_*.lean) and other
    problems' workareas never leak in."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.enqueue(conn, kind="Forward", target_id="p",
               target_kind="Problem", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE kind = 'Forward'", (db.now(),))
    conn.commit()
    conn.close()
    wa = workspace / ".attempts" / "aaaa-bbbb"
    wa.mkdir(parents=True)
    (wa / "Context.md").write_text("# Forward context — p\n\nbrief\n",
                                   encoding="utf-8")
    (wa / "new_forward.lean").write_text(
        "import Mathlib\n\ntheorem brick : True := trivial\n",
        encoding="utf-8")
    (wa / "_probe.lean").write_text("-- helper, never a draft\n",
                                    encoding="utf-8")
    other = workspace / ".attempts" / "cccc-dddd"
    other.mkdir(parents=True)
    (other / "Context.md").write_text("# Forward context — q\n",
                                      encoding="utf-8")
    (other / "new_forward.lean").write_text("-- wrong problem\n",
                                            encoding="utf-8")

    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    assert len(body["workers"]) == 1
    lane = body["workers"][0]
    assert lane["kind"] == "Forward"
    assert lane["path"] == ".attempts/aaaa-bbbb/new_forward.lean"
    assert "brick" in lane["file"]["tail"]


def test_run_strategist_lane_names_its_mode(
        workspace: Path, monkeypatch) -> None:
    """The Strategist lane says WHICH think this is: its Context.md
    already names the wake reason (`## Trigger` → trigger_kind), and
    the lane surfaces it as `mode` — 'reviewing results' reads very
    differently from 'routine look' (owner, 2026-07-12)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.enqueue(conn, kind="Strategist", target_id="p",
               target_kind="Problem", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE kind = 'Strategist'", (db.now(),))
    conn.commit()
    conn.close()
    wa = workspace / ".attempts" / "eeee-ffff"
    wa.mkdir(parents=True)
    (wa / "Context.md").write_text(
        "# Strategist context — p\n\n## Trigger\n\n"
        "`trigger_kind`: pending_review\n\nPending review on goal 7:\n",
        encoding="utf-8")

    # the agent drafts its plan note incrementally — the lane tails it
    # (design round K: the page went dead while the machine thought)
    (wa / "_plan.md").write_text(
        "## Plan\n\nweighing candidates for the torus route\n",
        encoding="utf-8")

    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    assert len(body["workers"]) == 1
    lane = body["workers"][0]
    assert lane["kind"] == "Strategist"
    assert lane["mode"] == "pending_review"
    assert lane["file"] is not None
    assert "weighing candidates" in lane["file"]["tail"]
    assert lane["path"].endswith("_plan.md")


def test_run_strategist_lane_names_its_group_not_a_row_id(
        workspace: Path, monkeypatch) -> None:
    """v35 — a Strategist seat belongs to a GROUP, so its queue row
    targets a group id. The lane's identity line must stay the thing a
    reader knows (the problem), with the group's charter naming the
    subject when it is a delegated one; the raw id read as a bare
    number where the problem name used to be (live, 2026-08-02)."""
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    top = _groups.ensure_top_group(conn, "p")
    sub = _groups.open_group(conn, problem="p", parent_group_id=top,
                             charter="settle the pigeonhole bound")
    db.enqueue(conn, kind="Strategist", target_id=str(sub),
               target_kind="Group", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE kind = 'Strategist'", (db.now(),))
    conn.commit()
    conn.close()
    _fake_daemon(monkeypatch, scope="p")
    lane = _client(workspace).get("/api/run").json()["workers"][0]
    assert lane["slug"] == "p"          # never the bare "17"
    assert lane["group"]["id"] == sub
    assert lane["group"]["is_top"] is False
    assert lane["group"]["charter"] == "settle the pigeonhole bound"


def test_run_strategist_lane_matches_on_its_one_context(
        workspace: Path, monkeypatch) -> None:
    """The wake ran in two turns from 2026-08-03 to 2026-08-11, and the
    ADMIN turn worked in `<workarea>/admin/` while the wake's own
    Context.md did not exist yet — so the console said "nothing on disk
    yet" about a working machine for up to ten minutes, and the lane
    grew a `stage` to name which turn it was in. With one turn there is
    one Context.md, matched directly, and `stage` is permanently null
    (kept in the payload so a stale UI bundle reads "no stage" rather
    than KeyError)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.enqueue(conn, kind="Strategist", target_id="p",
               target_kind="Problem", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE kind = 'Strategist'", (db.now(),))
    conn.commit()
    conn.close()
    wa = workspace / ".attempts" / "wake-1"
    wa.mkdir(parents=True)
    (wa / "Context.md").write_text(
        "# Strategist context — p\n\n## Trigger\n\n"
        "`trigger_kind`: routine\n", encoding="utf-8")
    _fake_daemon(monkeypatch, scope="p")

    lane = _client(workspace).get("/api/run").json()["workers"][0]
    assert lane["kind"] == "Strategist"
    assert lane["mode"] == "routine"
    assert lane["stage"] is None


def test_run_sibling_group_lanes_do_not_swap_thinking(
        workspace: Path, monkeypatch) -> None:
    """v35 — sibling groups run concurrently BY DESIGN, so one problem
    can have two Strategist workareas at once. Matching them by
    (kind, problem) alone made the pairing arbitrary: each lane could
    show the other group's plan note. The context compile stages
    `charter.md` for a sub-group and none for the top group, so the
    charter identifies the workarea."""
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    top = _groups.ensure_top_group(conn, "p")
    sub = _groups.open_group(conn, problem="p", parent_group_id=top,
                             charter="settle the pigeonhole bound")
    for gid in (top, sub):
        db.enqueue(conn, kind="Strategist", target_id=str(gid),
                   target_kind="Group", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE kind = 'Strategist'", (db.now(),))
    conn.commit()
    charter_md = _groups.charter_digest(conn, "p", sub)
    conn.close()

    # the sub-group's workarea is the one carrying charter.md
    sub_wa = workspace / ".attempts" / "sub-one"
    sub_wa.mkdir(parents=True)
    (sub_wa / "Context.md").write_text("# Strategist context — p\n",
                                       encoding="utf-8")
    (sub_wa / "charter.md").write_text(charter_md, encoding="utf-8")
    (sub_wa / "_plan.md").write_text("the pigeonhole route\n",
                                     encoding="utf-8")
    top_wa = workspace / ".attempts" / "top-one"
    top_wa.mkdir(parents=True)
    (top_wa / "Context.md").write_text("# Strategist context — p\n",
                                       encoding="utf-8")
    (top_wa / "_plan.md").write_text("the whole problem's route\n",
                                     encoding="utf-8")

    _fake_daemon(monkeypatch, scope="p")
    lanes = _client(workspace).get("/api/run").json()["workers"]
    by_group = {ln["group"]["id"]: ln for ln in lanes}
    assert "whole problem" in by_group[top]["file"]["tail"]
    assert "pigeonhole route" in by_group[sub]["file"]["tail"]


def test_run_goal_lane_prefers_the_fresher_workarea_draft(
        workspace: Path, monkeypatch) -> None:
    """A Backward attempt drafts patch.lean in its workarea and lands
    only at commit — the goal's own file is a static sorry stub the
    whole while. When the draft is fresher, the lane tails the draft;
    the workarea is matched by the '# Context for goal <slug>' heading
    (a sibling merely citing the slug never matches)."""
    import os
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="lemma_b",
                         lean_path="Problems/p/proofs/L_lemma_b.lean",
                         statement="b = b", origin="root")
    db.enqueue(conn, kind="Backward", target_id=str(gid),
               target_kind="Goal", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE target_id = ?", (db.now(), str(gid)))
    conn.commit()
    conn.close()
    landed = workspace / "Problems" / "p" / "proofs" / "L_lemma_b.lean"
    landed.parent.mkdir(parents=True)
    landed.write_text("import Mathlib\n\ntheorem lemma_b : b = b := by\n"
                      "  sorry\n", encoding="utf-8")
    os.utime(landed, (1_000_000, 1_000_000))  # old
    wa = workspace / ".attempts" / "eeee-ffff"
    wa.mkdir(parents=True)
    (wa / "Context.md").write_text(
        "# p — BRIEF\n\n# Context for goal lemma_b\n", encoding="utf-8")
    (wa / "patch.lean").write_text(
        "import Mathlib\n\ntheorem lemma_b : b = b := by\n"
        "  exact draft_progress\n", encoding="utf-8")

    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    lane = body["workers"][0]
    assert lane["path"] == ".attempts/eeee-ffff/patch.lean"
    assert "draft_progress" in lane["file"]["tail"]


def test_run_idle_keeps_telling_the_last_story(
        workspace: Path, monkeypatch) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.insert_goal(conn, problem="p", slug="done",
                   lean_path="Problems/p/proofs/done.lean",
                   statement="True", origin="root", status="proved")
    conn.commit()
    conn.close()
    _fake_daemon(monkeypatch, running=False,
                 last_exit={"at": db.now(), "rc": 0, "error": None,
                            "scope": "p"})
    body = _client(workspace).get("/api/run").json()
    assert body["problem"] == "p"
    assert body["goals"]["proved"] == 1
    assert body["workers"] == []
    assert body["burn_run"] is None


def test_problem_detail_signature_binders_and_alias_suppression(
        workspace: Path) -> None:
    """goals[].signature: binders from the stub; alias plumbing and
    binder-less matches fall back to null (statement stands)."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.insert_goal(conn, problem="p", slug="lemma_b",
                   lean_path="Problems/p/proofs/L_lemma_b.lean",
                   statement="q x", origin="backward", depth=1)
    db.insert_goal(conn, problem="p", slug="alias_g",
                   lean_path="Problems/p/proofs/L_alias_g.lean",
                   statement="r y", origin="backward", depth=1)
    conn.commit()
    conn.close()
    proofs = workspace / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / "L_lemma_b.lean").write_text(
        "import Mathlib\n\ntheorem lemma_b (x : Nat) (h : 0 < x) :\n"
        "    q x := by\n  sorry\n", encoding="utf-8")
    (proofs / "L_alias_g.lean").write_text(
        "import Mathlib\n\ndef alias_g := @Problems.p.s42\n",
        encoding="utf-8")
    body = _client(workspace).get("/api/problems/p").json()
    by_slug = {g["slug"]: g for g in body["goals"]}
    assert by_slug["lemma_b"]["signature"] == \
        "theorem lemma_b (x : Nat) (h : 0 < x) : q x"
    assert by_slug["lemma_b"]["statement"] == "q x"
    assert by_slug["alias_g"]["signature"] is None


def _verdict_json(**criteria: str) -> str:
    """A verdict file in the shape the ADVERSARY actually writes —
    every criterion adjudicated, unnamed ones clear. Hand-written
    fixtures are what let the console drift: the old test froze the
    pre-44ff4321 shape, stayed green, and the live console reported
    every rebut as `passed`."""
    import json as _json
    from Tooling.pipeline.adversary import (CRITERIA_KEYS,
                                            NAMING_CRITERIA)
    body = {"criteria": {k: criteria.get(
                             f"c{k}",
                             "clear: closer entry — nothing stands"
                             if k in NAMING_CRITERIA
                             else "clear: holds")
                         for k in CRITERIA_KEYS},
            "reservations": []}
    return _json.dumps(body)


def test_proposal_cycle_phases(tmp_path: Path) -> None:
    """_proposal_cycle narrates the proposal-Adversary argument from
    the wake's working files (research mode; display-only)."""
    from Tooling.serve.run import _proposal_cycle
    wa = tmp_path
    assert _proposal_cycle(wa) is None
    (wa / "proposal.md").write_text("# P\n", encoding="utf-8")
    c = _proposal_cycle(wa)
    assert c["phase"] == "proposing" and c["round"] == 0
    assert c["_tail_path"].endswith("proposal.md")
    r1 = wa / "adversary" / "r1"
    r1.mkdir(parents=True)
    (r1 / "proposal.md").write_text("# P\n", encoding="utf-8")
    c = _proposal_cycle(wa)
    assert c["phase"] == "judging" and c["round"] == 1
    (r1 / "verdict.json").write_text(
        _verdict_json(c2="fired: too vague", c4="fired: no experiment"),
        encoding="utf-8")
    c = _proposal_cycle(wa)
    assert c["phase"] == "revising" and c["round"] == 1
    # the fired criteria ARE the objections, tagged by the framework
    assert c["objections"] == ["[criterion 2] too vague",
                               "[criterion 4] no experiment"]
    r2 = wa / "adversary" / "r2"
    r2.mkdir(parents=True)
    (r2 / "proposal.md").write_text("# P2\n", encoding="utf-8")
    (r2 / "verdict.json").write_text(_verdict_json(), encoding="utf-8")
    c = _proposal_cycle(wa)
    assert c["phase"] == "passed" and c["round"] == 2
    assert c["objections"] == []


def test_proposal_cycle_never_invents_a_pass(tmp_path: Path) -> None:
    """A verdict the framework would REFUSE must not read as `passed`.

    The console's private copy of the verdict shape survived the
    per-criterion migration (44ff4321) by falling through to the pass
    branch: rounds that were rebutted displayed as "passed review;
    committing the programme" with the objections gone. Any file
    parse_verdict rejects leaves the phase at `judging` — the judge is
    genuinely still out, since the pipeline re-spawns it."""
    from Tooling.serve.run import _proposal_cycle
    r1 = tmp_path / "adversary" / "r1"
    r1.mkdir(parents=True)
    (r1 / "proposal.md").write_text("# P\n", encoding="utf-8")
    for bad in ('{"verdict": "rebut", "criticisms": ["legacy shape"]}',
                '{"criteria": {"1": "clear"}}',      # incomplete
                '{"criteria": {"1": "fired"}}',      # fired, no objection
                '{"criteria":'):                     # half-written
        (r1 / "verdict.json").write_text(bad, encoding="utf-8")
        assert _proposal_cycle(tmp_path)["phase"] == "judging", bad


# ---------------------------------------------------------------------
# the Theorist lane — a document under review, not a proposal
# ---------------------------------------------------------------------

def _theory_verdict_json(**fired: str) -> str:
    """A theory verdict in the shape the REVIEWER writes: four
    criteria, each a list of reasoned bullets. Built off the rubric's
    own keys so the fixture cannot freeze a shape the parser has moved
    past (the lesson `_verdict_json` carries)."""
    import json as _json
    from Tooling.pipeline.theorist.verdict import CRITERIA_KEYS
    body = {"criteria": {k: [fired[f"c{k}"]] if f"c{k}" in fired
                         else [f"clear: criterion {k} holds here"]
                         for k in CRITERIA_KEYS},
            "reservations": []}
    return _json.dumps(body)


def test_theory_cycle_phases(tmp_path: Path) -> None:
    """`_theory_cycle` narrates the author↔reviewer rounds from the
    Theorist workarea's own files: `report.md` at the root is the
    draft, `review/r<n>/` is each round's dossier and `verdict.json`
    inside it is the ruling — read through the theory verdict's OWN
    parser (`pipeline.theorist.verdict`), never a private copy."""
    from Tooling.serve.run import _theory_cycle
    wa = tmp_path
    assert _theory_cycle(wa) is None
    (wa / "report.md").write_text("# Doc\n\nfirst draft\n", encoding="utf-8")
    c = _theory_cycle(wa)
    assert c["phase"] == "drafting" and c["round"] == 0
    assert c["verdict"] is None
    assert c["_tail_path"].endswith("report.md")
    r1 = wa / "review" / "r1"
    r1.mkdir(parents=True)
    (r1 / "report.md").write_text("# Doc\n\nfirst draft\n", encoding="utf-8")
    c = _theory_cycle(wa)
    assert c["phase"] == "judging" and c["round"] == 1
    assert c["verdict"] is None
    # the on-trial copy is what the reviewer reads, so it is the tail
    assert Path(c["_tail_path"]) == r1 / "report.md"
    (r1 / "verdict.json").write_text(
        _theory_verdict_json(c2="fired: Theorem 1 is not proved",
                             c4="fired: no lead is tested"),
        encoding="utf-8")
    c = _theory_cycle(wa)
    assert c["phase"] == "revising" and c["round"] == 1
    assert c["verdict"] == "rebut"
    assert c["objections"] == ["[criterion 2] Theorem 1 is not proved",
                               "[criterion 4] no lead is tested"]
    # the author rewrites the ROOT report on the same session
    assert Path(c["_tail_path"]) == wa / "report.md"
    r2 = wa / "review" / "r2"
    r2.mkdir(parents=True)
    (r2 / "report.md").write_text("# Doc\n\nsecond draft\n", encoding="utf-8")
    (r2 / "verdict.json").write_text(_theory_verdict_json(),
                                     encoding="utf-8")
    c = _theory_cycle(wa)
    assert c["phase"] == "passed" and c["round"] == 2
    assert c["verdict"] == "pass"
    assert c["objections"] == []


def test_theory_cycle_never_invents_a_pass(tmp_path: Path) -> None:
    """A verdict the theory parser REFUSES leaves the reviewer out:
    the pipeline re-spawns it, so `judging` is the honest phase. Same
    law as the proposal cycle, under the other rubric — a bare `clear`
    and a mixed criterion are both refusals here."""
    from Tooling.serve.run import _theory_cycle
    r1 = tmp_path / "review" / "r1"
    r1.mkdir(parents=True)
    (r1 / "report.md").write_text("# Doc\n", encoding="utf-8")
    for bad in ('{"verdict": "pass"}',
                '{"criteria": {"1": ["clear"], "2": ["clear: x"],'
                ' "3": ["clear: x"], "4": ["clear: x"]}}',   # bare clear
                '{"criteria": {"1": ["clear: x", "fired: y"],'
                ' "2": ["clear: x"], "3": ["clear: x"], "4": ["clear: x"]}}',
                '{"criteria":'):
        (r1 / "verdict.json").write_text(bad, encoding="utf-8")
        c = _theory_cycle(tmp_path)
        assert c["phase"] == "judging" and c["verdict"] is None, bad


def test_run_theorist_lane_streams_the_draft_and_the_review(
        workspace: Path, monkeypatch) -> None:
    """The Theorist card was the one slot with no live view: its
    workarea holds no `.lean`, no `_plan.md` and no `proposal.md`, so
    the lane fell through every reader and said "nothing on disk yet"
    for the whole of an author turn. The lane now tails the document
    the author is writing (`report.md`) and narrates the review rounds
    (`review/r<n>/verdict.json`) the way a Strategist lane narrates its
    proposal cycle — round number, last verdict, the fired objections.
    """
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    top = _groups.ensure_top_group(conn, "p")
    db.enqueue(conn, kind="Theorist", target_id=str(top),
               target_kind="Group", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE kind = 'Theorist'", (db.now(),))
    db.record_pipeline_start(conn, pipeline_id="th-live", kind="Theorist",
                             target_id=str(top), target_kind="Group")
    conn.commit()
    conn.close()
    wa = workspace / ".attempts" / "th-live"
    wa.mkdir(parents=True)
    (wa / "Context.md").write_text("# p — BRIEF\n\n## Trigger\n\n"
                                   "`trigger_kind`: theory\n",
                                   encoding="utf-8")
    (wa / "report.md").write_text(
        "# The unit-imbalance erasure\n\n## Abstract\n\n"
        "It reduces MAIN to a smaller claim.\n", encoding="utf-8")
    r1 = wa / "review" / "r1"
    r1.mkdir(parents=True)
    (r1 / "report.md").write_text("# The unit-imbalance erasure\n",
                                  encoding="utf-8")
    (r1 / "verdict.json").write_text(
        _theory_verdict_json(c2="fired: Theorem 1 is not proved"),
        encoding="utf-8")

    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    assert len(body["workers"]) == 1
    lane = body["workers"][0]
    assert lane["kind"] == "Theorist"
    assert lane["pipeline_id"] == "th-live"
    assert lane["path"] == ".attempts/th-live/report.md"
    assert "reduces MAIN" in lane["file"]["tail"]
    assert lane["cycle"]["phase"] == "revising"
    assert lane["cycle"]["round"] == 1
    assert lane["cycle"]["verdict"] == "rebut"
    assert lane["cycle"]["objections"] == [
        "[criterion 2] Theorem 1 is not proved"]


def test_context_preamble_extraction() -> None:
    """_context_preamble: opens + multi-line variable block ride along;
    docstring prose starting with "open" does not leak in."""
    from Tooling.serve.data import _context_preamble, _scan_library_file
    text = (
        "import Mathlib\n\n"
        "/-! # Module\nopen problems are listed here\n-/\n\n"
        "open Bundle MeasureTheory\n"
        "open scoped Manifold Topology\n\n"
        "namespace Lib.X\n\n"
        "variable {d : Nat} {EH : Type _} [TopologicalSpace EH]\n"
        "    {N : Type _} [TopologicalSpace N] [T2Space N]\n\n"
        "/-- doc -/\n"
        "theorem foo (p : N) : True := trivial\n")
    pos = text.index("theorem foo")
    ctx = _context_preamble(text, pos)
    assert "open Bundle MeasureTheory" in ctx
    assert "open scoped Manifold Topology" in ctx
    assert "[TopologicalSpace N] [T2Space N]" in ctx  # continuation line
    assert "open problems are listed" not in ctx      # docstring prose
    assert "namespace" not in ctx                     # ns handled by seed
    _, docs, _, ctx2 = _scan_library_file(text)
    assert ctx2 == ctx and "foo" in docs


def test_pattern_scope_resolves_to_real_problems(
        workspace: Path, monkeypatch) -> None:
    """A wildcard scope must never reach the UI as the focus problem —
    it 404s the detail fetch and blanks the sky. Candidates: leased
    problems first, then pattern matches; ?problem= picks the lens."""
    conn = _open_db(workspace)
    _add_problem(conn, "Cmp.a")
    _add_problem(conn, "Cmp.b")
    ga = db.insert_goal(conn, problem="Cmp.a", slug="g_a",
                        lean_path="Problems/Cmp/a/proofs/L_g_a.lean",
                        statement="a", origin="root")
    db.enqueue(conn, kind="Builder", target_id=str(ga),
               target_kind="Goal", problem="Cmp.a")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE target_id = ?", (db.now(), str(ga)))
    conn.commit()
    conn.close()
    _fake_daemon(monkeypatch, running=True, pid=4321, scope="Cmp.%")
    body = _client(workspace).get("/api/run").json()
    assert body["problem"] == "Cmp.a"           # leased problem wins
    assert set(body["problems"]) == {"Cmp.a", "Cmp.b"}
    assert body["workers"][0]["problem"] == "Cmp.a"
    picked = _client(workspace).get("/api/run?problem=Cmp.b").json()
    assert picked["problem"] == "Cmp.b"
    bogus = _client(workspace).get("/api/run?problem=No.such").json()
    assert bogus["problem"] == "Cmp.a"          # bad pick falls back


# ---------------------------------------------------------------------
# GET /api/run/events — the Timeline, run-flavoured
# ---------------------------------------------------------------------
#
# Two framings of one renderer (the shape `419dcb31` settled when the
# Programme joined this page): the problem page keeps the archive, the
# Engine reads the run you sit on. The console cannot delegate this to
# the problem page — a pattern scope runs several problems at once and
# a problem page can only ever show one.

def _problem(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)", (name, db.now()))
    conn.commit()


def test_run_events_span_every_problem_under_a_pattern_scope(
        workspace: Path, monkeypatch) -> None:
    conn = _open_db(workspace)
    for name in ("Cmp.a", "Cmp.b"):
        _problem(conn, name)
        gid = db.insert_goal(conn, problem=name, slug=f"brick_{name[-1]}",
                             lean_path=f"proofs/{name}.lean", statement="True",
                             origin="forward")
        db.update_goal_status(conn, gid, "proved", event="builder_proved")
    conn.close()
    _fake_daemon(monkeypatch, scope="Cmp.%")
    d = _client(workspace).get("/api/run/events").json()
    assert set(d["problems"]) == {"Cmp.a", "Cmp.b"}
    # every row says which problem it belongs to — the merge is
    # meaningless otherwise
    assert {(e["problem"], e["label"]) for e in d["events"]
            if e["kind"] == "proved"} == {
        ("Cmp.a", "brick_a"), ("Cmp.b", "brick_b")}


def test_run_events_draw_no_seam_across_several_problems(
        workspace: Path, monkeypatch) -> None:
    """The reconstruction boundary is a PER-PROBLEM fact ('the engine
    started recording here'). Merged, there is no single line to draw,
    so the run view draws none and the rows keep their own marks."""
    conn = _open_db(workspace)
    for name in ("Cmp.a", "Cmp.b"):
        _problem(conn, name)
        gid = db.insert_goal(conn, problem=name, slug=f"brick_{name[-1]}",
                             lean_path=f"proofs/{name}.lean", statement="True",
                             origin="forward")
        db.update_goal_status(conn, gid, "proved", event="builder_proved")
    conn.close()
    _fake_daemon(monkeypatch, scope="Cmp.%")
    assert _client(workspace).get("/api/run/events").json()["log_since"] is None
    # one problem in scope → the seam is meaningful again
    _fake_daemon(monkeypatch, scope="Cmp.a")
    d = _client(workspace).get("/api/run/events").json()
    assert d["problems"] == ["Cmp.a"]
    assert d["log_since"] is not None


def test_run_events_empty_workspace_is_not_an_error(
        workspace: Path, monkeypatch) -> None:
    _fake_daemon(monkeypatch, running=False)
    r = _client(workspace).get("/api/run/events")
    assert r.status_code == 200
    assert r.json()["events"] == []


def test_scratch_drafts_identified_by_pipeline_row_not_title(
    workspace: Path,
) -> None:
    """The worker Context.md header became `# <problem> — BRIEF`
    (2026-08-26) and the title regex silently dropped every mint /
    direct workarea from the lanes — the Engine Console card fell back
    to static copy. The dir name IS the pipeline id: the DB row is the
    signal; the title regex survives only as fallback for dirs the DB
    does not know."""
    from Tooling.serve.run import _scratch_drafts
    conn = _open_db(workspace)
    _add_problem(conn, "P.x")
    gid = db.insert_goal(conn, problem="P.x", slug="g",
                         lean_path="Problems/P.x/proofs/L_g.lean",
                         statement="T", origin="backward")
    db.record_pipeline_start(conn, pipeline_id="aaaa-mint", kind="Formalizer",
                             target_id=str(gid), target_kind="Goal")
    att = workspace / ".attempts"
    # 1) mint workarea, BRIEF header, KNOWN to the DB → identified
    d1 = att / "aaaa-mint"
    d1.mkdir(parents=True)
    (d1 / "Context.md").write_text("# P.x — BRIEF\nbody", encoding="utf-8")
    # 2) unknown dir with the OLD title shape → fallback still works
    d2 = att / "bbbb-old"
    d2.mkdir()
    (d2 / "Context.md").write_text("# Strategist context — P.x\n",
                                   encoding="utf-8")
    # 3) unknown dir, BRIEF header → nothing to identify, skipped
    d3 = att / "cccc-unknown"
    d3.mkdir()
    (d3 / "Context.md").write_text("# P.x — BRIEF\n", encoding="utf-8")

    got = {(t[0], t[1], t[3].name) for t in _scratch_drafts(conn, workspace)}
    assert ("Formalizer", "P.x", "aaaa-mint") in got
    assert ("Strategist", "P.x", "bbbb-old") in got
    assert not any(name == "cccc-unknown" for _, _, name in got)
    conn.close()


def test_the_recent_feed_says_who_decided(workspace: Path,
                                          monkeypatch) -> None:
    """The run console's decision feed is the third surface a decision
    row is serialised on (HID §3.2). Without `actor` a person's park and
    the machine's read identically here."""
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    ts = db.now()
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, outcome, actor, created_at,"
        " updated_at) VALUES ('p', 0, 'human', 'ConfirmShelve', 'success',"
        " 'human', ?, ?)", (ts, ts))
    conn.commit()
    conn.close()
    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    assert body["recent"][0]["actor"] == "human"


# ---------------------------------------------------------------------
# the meters never ride the request (2026-09-03)
# ---------------------------------------------------------------------

def test_the_meters_refresh_off_the_request_thread(
        workspace: Path, monkeypatch) -> None:
    """A quota miss made `/api/run` wait on api.anthropic.com (+1.1s
    once a minute), and the session-log meter walked the preserved
    rollouts inside the same request. Both are garnish: the request
    serves what the meter last read and the reading is refreshed on a
    thread of its own — a request must never wait on a meter."""
    import threading

    from Tooling.core import usage_quota
    from Tooling.serve import run as _run

    names: "list[str]" = []
    done = threading.Event()

    def fetch():
        names.append(threading.current_thread().name)
        done.set()
        return None

    def walk(ws):  # noqa: ANN001
        names.append(threading.current_thread().name)
        return []

    monkeypatch.setattr(_run, "_fetch_oauth_usage", fetch)
    monkeypatch.setattr(usage_quota, "session_log_usage", walk)
    _run.reset_quota_memo()

    r = _client(workspace).get("/api/run")
    assert r.status_code == 200
    assert r.json()["quota"] is None
    assert done.wait(10.0), "the meter never refreshed"
    assert names, "the meter was never read at all"
    assert all(n.startswith("asterism-meter") for n in names), names


# ---------------------------------------------------------------------
# the run read is a PROJECT surface (HID §1.4) — 2026-09-03
# ---------------------------------------------------------------------

def _shelved_problem(conn: sqlite3.Connection, name: str,
                     project: str) -> None:
    conn.execute("INSERT OR IGNORE INTO projects (name, description,"
                 " created_at) VALUES (?, '', ?)", (project, db.now()))
    conn.execute("INSERT INTO problems (name, project, created_at)"
                 " VALUES (?, ?, ?)", (name, project, db.now()))
    conn.commit()


def _leased_goal(conn: sqlite3.Connection, problem: str, slug: str) -> int:
    gid = db.insert_goal(conn, problem=problem, slug=slug,
                         lean_path=f"Problems/{problem}/proofs/{slug}.lean",
                         statement="True", origin="root")
    db.enqueue(conn, kind="Builder", target_id=str(gid),
               target_kind="Goal", problem=problem)
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE target_id = ?", (db.now(), str(gid)))
    conn.commit()
    return gid


def test_the_run_read_shows_only_the_named_projects_work(
        workspace: Path, monkeypatch) -> None:
    """The Engine Room lives INSIDE a Project, and `/api/run` had no
    project at all — its problem set was the daemon's scope, so a run
    over another shelf filled this one's lanes, tallies, feed and burn
    with another Project's work (and the lane links pointed INTO this
    Project at another Project's task). Everything the shelf shows is
    scoped by `problems.project`; daemon liveness and the account
    meters stay workspace-wide, because they are."""
    conn = _open_db(workspace)
    _shelved_problem(conn, "Mine.a", "Mine")
    _shelved_problem(conn, "Yours.b", "Yours")
    _leased_goal(conn, "Mine.a", "g_mine")
    _leased_goal(conn, "Yours.b", "g_yours")
    conn.close()
    _fake_daemon(monkeypatch, running=True, pid=4321, scope="Mine.a,Yours.b")

    body = _client(workspace).get("/api/run?project=Mine").json()
    assert body["problems"] == ["Mine.a"]
    assert body["problem"] == "Mine.a"
    assert [w["problem"] for w in body["workers"]] == ["Mine.a"]
    assert body["goals"]["total"] == 1
    # the engine's own state is not a per-shelf fact
    assert body["daemon"]["running"] is True


def test_the_run_feed_shows_only_the_named_projects_events(
        workspace: Path, monkeypatch) -> None:
    """`/api/run/events` resolves its problem set through the same
    `_resolve_focus`, so it inherited the same leak."""
    conn = _open_db(workspace)
    for name, shelf in (("Mine.a", "Mine"), ("Yours.b", "Yours")):
        _shelved_problem(conn, name, shelf)
        gid = db.insert_goal(conn, problem=name, slug=f"brick_{shelf}",
                             lean_path=f"proofs/{name}.lean",
                             statement="True", origin="forward")
        db.update_goal_status(conn, gid, "proved", event="builder_proved")
    conn.close()
    _fake_daemon(monkeypatch, running=True, pid=4321, scope="Mine.a,Yours.b")

    d = _client(workspace).get("/api/run/events?project=Mine").json()
    assert d["problems"] == ["Mine.a"]
    assert {e["problem"] for e in d["events"]} <= {"Mine.a"}
