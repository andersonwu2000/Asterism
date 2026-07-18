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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()))
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


def test_run_fresh_workspace_is_quiet(workspace: Path) -> None:
    r = _client(workspace).get("/api/run")
    assert r.status_code == 200
    body = r.json()
    assert body["workers"] == []
    assert body["goals"] is None
    # quota is garnish: offline → null, never an error
    assert body["quota"] is None


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
        '{"verdict": "rebut", "criticisms": ["too vague", "no experiment"]}',
        encoding="utf-8")
    c = _proposal_cycle(wa)
    assert c["phase"] == "revising" and c["round"] == 1
    assert c["objections"] == ["too vague", "no experiment"]
    r2 = wa / "adversary" / "r2"
    r2.mkdir(parents=True)
    (r2 / "proposal.md").write_text("# P2\n", encoding="utf-8")
    (r2 / "verdict.json").write_text(
        '{"verdict": "pass", "reservations": []}', encoding="utf-8")
    c = _proposal_cycle(wa)
    assert c["phase"] == "passed" and c["round"] == 2
    assert c["objections"] == []
