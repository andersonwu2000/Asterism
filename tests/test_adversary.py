"""Research mode P1 — the proposal-package gate + Adversary cycle
(research_mode_design.md §1/§3).

Covers: gate shape (exempt kinds / audit trigger / experiment rule),
the rebut→revise→pass round trip (dialogue recorded, rev advances,
fresh judge per round), exhaustion → strategist_proposal_rejected with
the discarded proposal + criticisms in programme_revisions, and the
projection's isolation-relevant contents. Mirrors
test_phase2_run_pipelines fixtures (mocked spawn_llm, everything else
real).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from Tooling import agent
from Tooling.pipeline import adversary, strategist
from Tooling.state import db, manifest, programme


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    (pdir / "proofs").mkdir()
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done) VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


@pytest.fixture
def mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="T")


def _insert_root(conn: sqlite3.Connection) -> int:
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean", statement="T",
        origin="root", depth=0, entry_kind="Backward",
    )


def _d(kind: str, **kw) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, pipeline=kw.get("pipeline"),
                           target_id=kw.get("target_id"),
                           brief=kw.get("brief"), body=kw.get("body"),
                           reason=kw.get("reason"))


_PROPOSAL = ("# Step\n## Argument\nWhy this batch.\n"
             "## Roadmap\n1. the brick\n## Thesis\nThe route holds.\n")


# -------------------------------------------------------------- gate

def test_gate_shape():
    assert not strategist.package_gate_applies(
        [_d("FetchPaper"), _d("Noop")], "routine")
    assert not strategist.package_gate_applies(
        [_d("RequestUserAmend")], "pending_review")
    # Any route-moving kind arms the gate — including EmitDirective
    # (the drift side door) and the endgame kinds.
    for kind in ("Inject", "AttemptDisproof", "ConfirmShelve",
                 "MarkDeliverable", "Ingest", "EmitDirective"):
        assert strategist.package_gate_applies(
            [_d(kind), _d("Noop")], "routine"), kind
    # Audit wakes sit wholly outside the gate.
    assert not strategist.package_gate_applies(
        [_d("EmitDirective")], "audit")


def test_package_requires_file_and_experiment(tmp_path: Path):
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", pipeline="Forward", brief="b")], tmp_path)
    assert body is None and "proposal.md" in err

    (tmp_path / "proposal.md").write_text(_PROPOSAL, encoding="utf-8")
    # EmitDirective-only (no experiment, not endgame) → rejected.
    body, sections, err = strategist.verify_proposal_package(
        [_d("EmitDirective", body="x")], tmp_path)
    assert body is None and "experiment" in err
    # Endgame batches are exempt from the experiment rule.
    body, sections, err = strategist.verify_proposal_package(
        [_d("Ingest")], tmp_path)
    assert err is None and body == _PROPOSAL
    # AttemptDisproof counts as the experiment (no brief → no tag rule).
    body, sections, err = strategist.verify_proposal_package(
        [_d("AttemptDisproof")], tmp_path)
    assert err is None
    # Inject briefs must name an existing Roadmap entry (P2 check).
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", brief="## Need\nx")], tmp_path)
    assert body is None and "Roadmap:" in err
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", brief="Roadmap: no such entry\n## Need\nx")],
        tmp_path)
    assert body is None and "no such entry" in err
    body, sections, err = strategist.verify_proposal_package(
        [_d("Inject", brief="Roadmap: the brick\n## Need\nx")], tmp_path)
    assert err is None


# ------------------------------------------------- verdict contract

def test_parse_verdict_contract():
    v, err = adversary.parse_verdict(
        json.dumps({"verdict": "pass"}))
    assert err == "" and v["reservations"] == [] and v["criticisms"] == []
    v, err = adversary.parse_verdict(
        json.dumps({"verdict": "rebut", "criticisms": ["weak step 2"]}))
    assert err == "" and v["criticisms"] == ["weak step 2"]
    for bad in ("not json", json.dumps(["x"]),
                json.dumps({"verdict": "maybe"}),
                json.dumps({"verdict": "rebut"}),
                json.dumps({"verdict": "pass", "reservations": [1]})):
        v, err = adversary.parse_verdict(bad)
        assert v is None and err


# ------------------------------------- full cycle via run_strategist

def _spawn_script(rebuttals_before_pass: int):
    """A scripted spawn_llm: the strategist writes an Inject batch +
    proposal (revising the title per round); the adversary rebuts N
    times, then passes with one reservation. Captures adversary
    session ids to assert fresh-per-round."""
    state = {"adversary_calls": 0, "adversary_sids": [],
             "strategist_calls": 0}

    def fake_spawn(**kw):
        if kw.get("kind") == "adversary":
            state["adversary_calls"] += 1
            state["adversary_sids"].append(kw.get("session_id"))
            if state["adversary_calls"] <= rebuttals_before_pass:
                verdict = {"verdict": "rebut",
                           "criticisms": [
                               f"objection {state['adversary_calls']}"]}
            else:
                verdict = {"verdict": "pass",
                           "reservations": ["watch the sign"]}
            (kw["attempts_dir"] / "verdict.json").write_text(
                json.dumps(verdict), encoding="utf-8")
            return 0
        state["strategist_calls"] += 1
        n = state["strategist_calls"]
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "Inject", "pipeline": "Forward",
                        "brief": f"Roadmap: the brick\n## Need\nbrick v{n}"}),
            encoding="utf-8")
        (kw["attempts_dir"] / "proposal.md").write_text(
            _PROPOSAL.replace("# Step", f"# Step v{n}"),
            encoding="utf-8")
        return 0

    return fake_spawn, state


def test_rebut_then_pass_advances_rev(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_root(conn)
    fake, state = _spawn_script(rebuttals_before_pass=1)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id="adv-1",
    )
    assert r.outcome == "success"
    # One rebuttal round: 2 strategist spawns, 2 adversary spawns,
    # each adversary round on a FRESH session id.
    assert state["strategist_calls"] == 2
    assert state["adversary_calls"] == 2
    assert len(set(state["adversary_sids"])) == 2

    row = programme.current_rev(conn, "p")
    assert row is not None and row["rev"] == 1
    assert "# Step v2" in row["body"]  # the revised proposal passed
    assert row["rounds"] == 1
    assert row["batch_id"] is not None
    verdict = json.loads(row["verdict"])
    assert verdict["reservations"] == ["watch the sign"]
    dialogue = json.loads(row["dialogue"])
    assert dialogue[0]["criticisms"] == ["objection 1"]
    assert "# Step v1" in dialogue[0]["proposal"]
    # Render landed beside the problem files.
    rendered = (workspace / "Problems" / "p" / "PROGRAMME.md")
    assert rendered.exists()
    assert "watch the sign" in rendered.read_text(encoding="utf-8")


def test_exhaustion_records_rejection(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_root(conn)
    monkeypatch.setenv("ASTERISM_STRATEGIST_VERIFY_RETRY", "2")
    fake, state = _spawn_script(rebuttals_before_pass=99)
    monkeypatch.setattr(agent, "spawn_llm", fake)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id="adv-2",
    )
    assert r.outcome == "failed"
    assert r.failure_reason == "strategist_proposal_rejected"
    # No rev passed; the rejected row keeps proposal + full dialogue.
    assert programme.current_rev(conn, "p") is None
    row = conn.execute(
        "SELECT * FROM programme_revisions WHERE problem='p'"
        " AND status='rejected'").fetchone()
    assert row is not None and row["rounds"] == 2
    dialogue = json.loads(row["dialogue"])
    assert [e["criticisms"] for e in dialogue] == [
        ["objection 1"], ["objection 2"], ["objection 3"]]
    # Next wake gets the one-line record, never the draft.
    notice = programme.rejection_notice(conn, "p")
    assert notice and "rejected" in notice
    # No commit happened: no strategist_decisions row for the batch,
    # and the stall anchor (last_strategist_at ratchet) did not move —
    # a rejected wake stays visible to the cross-wake no-delta
    # machinery (design §1: 被拒 wake 計入跨-wake 無 delta 序列).
    assert conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions WHERE problem='p'"
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT last_strategist_at FROM problems WHERE name='p'"
    ).fetchone()[0] is None


def test_exempt_batch_skips_adversary(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Noop-only batch (wholly exempt kinds) never spawns the
    Adversary and needs no proposal.md."""
    _insert_root(conn)
    calls = {"adversary": 0}

    def fake_spawn(**kw):
        if kw.get("kind") == "adversary":
            calls["adversary"] += 1
            return 0
        (kw["attempts_dir"] / "decision.json").write_text(
            json.dumps({"kind": "Noop", "reason": "work in flight"}),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = strategist.run_strategist(
        conn, problem="p", trigger_kind="routine", tick=1,
        workspace=workspace, mfst=mfst, pipeline_id="adv-3",
    )
    assert r.failure_reason == "strategist_noop"
    assert calls["adversary"] == 0


# -------------------------------------------------- context surfaces

def test_context_surfaces(workspace: Path, conn: sqlite3.Connection):
    from Tooling.agent import context as wctx
    from Tooling.agent import phase2_context

    # Bootstrap: strategist sees the founding line; workers see nothing.
    boot = "\n".join(phase2_context._section_programme_strategist(conn, "p"))
    assert "rev 1" in boot and "none yet" in boot
    assert wctx._section_programme_worker(conn, "p", None) == []

    programme.record_pass(
        conn, "p", _PROPOSAL,
        {"verdict": "pass", "reservations": ["watch the sign"]},
        [], 1, "b1")
    s = "\n".join(phase2_context._section_programme_strategist(conn, "p"))
    assert "rev 1" in s and "## Thesis" in s and "watch the sign" in s
    w = "\n".join(wctx._section_programme_worker(conn, "p", None))
    assert "PROGRAMME.md" in w and "watch the sign" in w

    # After a discarded cycle the strategist gets the one-line record.
    programme.record_rejection(conn, "p", _PROPOSAL, [], 3)
    s2 = "\n".join(phase2_context._section_programme_strategist(conn, "p"))
    assert "Previous proposal rejected" in s2

    # Dangling pointer heals: rev in DB, file gone → the worker
    # section re-renders idempotently before advertising it.
    pdir = workspace / "Problems" / "p"
    rendered = pdir / "PROGRAMME.md"
    if rendered.exists():
        rendered.unlink()
    w2 = "\n".join(wctx._section_programme_worker(conn, "p", None, pdir))
    assert "PROGRAMME.md" in w2
    assert rendered.exists()


# ------------------------------------------------------- projection

def test_projection_contents(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    attempts = workspace / ".attempts" / "adv-proj"
    attempts.mkdir(parents=True)
    pdir = workspace / "Problems" / "p"
    # CATALOG.md never lives in problem_dir — the projection generates
    # it from goal records (07-19: the old problem_dir copy was dead
    # code and the judge never saw the landed-brick list).
    db.insert_goal(
        conn, problem="p", slug="brick_a",
        lean_path="Problems/p/proofs/L_brick_a.lean",
        statement="theorem brick_a : 1 + 1 = 2", origin="forward",
        depth=1, status="proved")
    # formal ground truth rides along read-only (user call 07-19)
    (pdir / "Root.lean").write_text("theorem main : T := by sorry\n",
                                    encoding="utf-8")
    (pdir / "Defs.lean").write_text("def f := 1\n", encoding="utf-8")

    proj = adversary.build_projection(
        round_no=2, attempts_dir=attempts, problem_dir=pdir,
        conn=conn, problem="p", proposal_body=_PROPOSAL,
        decisions=[_d("Inject", pipeline="Forward", brief="## Need\nx")],
        dialogue=[{"round": 1, "role": "adversary",
                   "criticisms": ["too vague"], "proposal": "# old"}],
        thesis_warn="WARN: long thesis")

    assert proj == attempts / "adversary" / "r2"
    assert (proj / "Manifest.md").exists()
    cat = (proj / "CATALOG.md").read_text(encoding="utf-8")
    assert "brick_a" in cat and "Proved catalog" in cat
    assert (proj / "Root.lean").exists()
    assert (proj / "Defs.lean").exists()
    # PROGRAMME.md = current rev (bootstrap placeholder here) + its
    # execution record, welded into one file.
    prog = (proj / "PROGRAMME.md").read_text(encoding="utf-8")
    assert "rev 1" in prog
    assert "Completed Inject batches" in prog
    assert not (proj / "outcomes.md").exists()
    assert "WARN: long thesis" in (proj / "proposal.md").read_text(
        encoding="utf-8")
    assert "Inject(Forward)" in (proj / "decisions.md").read_text(
        encoding="utf-8")
    d = (proj / "dialogue.md").read_text(encoding="utf-8")
    assert "too vague" in d and "# old" in d


# ---------------------------------------------------------------------
# spawn_usage attribution (invisible-judge class, 2026-07-18)
# ---------------------------------------------------------------------

def test_record_spawn_usage_explicit_attribution(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The Adversary spawns into a projection dir nested inside another
    pipeline's attempts dir — layout-derived attribution pointed the
    workspace at `.attempts/<pid>/` and silently dropped every judge
    row (b6: ~0.5h invisible). Explicit params must land the row on the
    real problem, tied to the host strategist pipeline."""
    from Tooling.agent.runtime import _record_spawn_usage
    strategist_attempts = workspace / ".attempts" / "pid-strat-7"
    proj = strategist_attempts / "adversary" / "r3"
    proj.mkdir(parents=True)
    (proj / "_parser_state.json").write_text(
        json.dumps({"usage": {"turns": 4, "output_tokens": 1234,
                              "input_tokens": 56}}),
        encoding="utf-8")

    _record_spawn_usage(
        kind="adversary", attempts_dir=proj, problem_dir=proj,
        wall_sec=12.5, workspace=workspace, problem="p",
        pipeline_id=strategist_attempts.name)

    row = conn.execute("SELECT * FROM spawn_usage").fetchone()
    assert row is not None
    assert row["problem"] == "p"
    assert row["kind"] == "adversary"
    assert row["pipeline_id"] == "pid-strat-7"
    assert row["output_tokens"] == 1234


def test_record_spawn_usage_never_mints_a_junk_db(
    workspace: Path,
) -> None:
    """Without explicit params the old code derived a wrong workspace
    and `connect()` CREATED an empty sqlite file there. A derived
    workspace with no asterism.db must be a silent no-op, not a mint."""
    from Tooling.agent.runtime import _record_spawn_usage
    proj = workspace / ".attempts" / "pid-x" / "adversary" / "r1"
    proj.mkdir(parents=True)
    (proj / "_parser_state.json").write_text(
        json.dumps({"usage": {"turns": 1, "output_tokens": 9}}),
        encoding="utf-8")

    _record_spawn_usage(kind="adversary", attempts_dir=proj,
                        problem_dir=proj, wall_sec=1.0)

    # derived workspace = proj.parent.parent = .attempts/pid-x — the
    # guard must not have created an asterism.db there
    assert not (workspace / ".attempts" / "pid-x" / "asterism.db").exists()
