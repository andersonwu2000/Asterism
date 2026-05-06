"""Backward pipeline tests covering spawn args, leaf-bypass, F55
postmortem, and the .drafts/ persist/clear policy.

Phase 7 retired the cross-pipeline session_id mechanism (former F53 /
F53A) and Phase 7-D dropped the `goals.backward_session_id` column
entirely: the agent session now lives within one pipeline call, sid
is a local var in the retry helper. The helper's behavior is
exercised directly by `test_pipeline_retry_helper.py`; this file
covers the Backward-specific outer wrapper (skeleton write, leaf-
bypass, .drafts/ policy, postmortem dispatch).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import agent, db, manifest, pipeline


def _seed_root_goal(tmp_path: Path, conn: sqlite3.Connection) -> int:
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n## Statement\nTrue\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) "
        "VALUES (?, ?, ?)",
        (problem, str(pdir / "Manifest.md"), db.now()))
    conn.commit()
    root = pdir / "Root.lean"
    root.write_text(
        "import Mathlib\nnamespace Problems.p\n"
        "theorem main : True := by sorry\n"
        "end Problems.p\n",
        encoding="utf-8")
    rel = root.relative_to(tmp_path).as_posix()
    return db.insert_goal(
        conn, problem=problem, slug="main", lean_path=rel,
        statement="True", origin="root", depth=0,
    )


def test_first_dispatch_mints_session_id_and_passes_to_spawn(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First retry-loop iteration is cold: helper mints a fresh sid
    and passes it with is_retry=False / retry_context=None."""
    gid = _seed_root_goal(tmp_path, conn)
    captured = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 124  # bail out via timeout path; we only care about call args

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw1",
    )
    assert captured["session_id"] is not None
    assert captured["is_retry"] is False
    assert captured["retry_context"] is None


def test_each_dispatch_mints_fresh_strategy_id(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 7 — every Backward dispatch reserves a fresh strategy_id
    (no cross-pipeline reuse of dead strategies). The retired F53/A
    reuse logic was a workaround for cross-pipeline session memory
    anchoring on a stale theorem name; in-pipeline retry shares one
    sid + one strategy_id within a single pipeline call, so cross-
    pipeline always gets fresh ids."""
    gid = _seed_root_goal(tmp_path, conn)
    rel = db.get_goal(conn, gid)["lean_path"]
    stale_sid = db.insert_strategy(
        conn, goal_id=gid, lean_path=rel,
        created_by="pid-old", proposal_md="", scratch_path="",
    )
    db.update_strategy_status(conn, stale_sid, "dead")

    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 124)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-cold",
    )
    rows = conn.execute(
        "SELECT id FROM strategies WHERE goal_id=? ORDER BY id",
        (gid,),
    ).fetchall()
    # Expect: stale + freshly-minted (different ids)
    assert len(rows) == 2
    assert rows[0]["id"] == stale_sid
    assert rows[1]["id"] != stale_sid


# ---------------------------------------------------------------------
# F55 — wrapper persists/clears partial PROPOSAL.md per outcome
# ---------------------------------------------------------------------

def _bw_drafts_path(tmp_path: Path, gid: int) -> Path:
    return tmp_path / "Problems" / "p" / ".drafts" / f"backward_g{gid}.md"


def test_backward_wrapper_persists_progress_note_after_timeout(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 — main Backward spawn times out (rc=124). Framework runs a
    postmortem spawn that resumes the killed session and writes
    _progress.md with state + blockers. Wrapper persists _progress.md
    into .drafts/ so the next dispatch's Context.md surfaces it."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        if kw.get("is_postmortem"):
            (kw["attempts_dir"] / "_progress.md").write_text(
                "Kelly minimiser route, 4 sub-goals; blocked on the "
                "perpendicular-distance lemma name.",
                encoding="utf-8")
            return 0
        return 124  # main timeout
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-timeout")
    draft = _bw_drafts_path(tmp_path, gid)
    assert draft.exists()
    body = draft.read_text(encoding="utf-8")
    assert "Kelly minimiser" in body
    assert "perpendicular-distance" in body


def test_backward_timeout_dispatches_postmortem_with_correct_args(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 — on main-spawn timeout, framework calls spawn_llm a second
    time with is_postmortem=True, prompt_path pointing at
    backward_postmortem.md, and the same session_id as the killed
    main spawn (so --resume can revive its memory)."""
    gid = _seed_root_goal(tmp_path, conn)
    calls = []

    def fake_spawn(**kw):
        calls.append(kw)
        if kw.get("is_postmortem"):
            return 124  # don't bother writing — just inspect args
        return 124  # main timeout
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-pm-args")
    assert len(calls) == 2  # main + postmortem
    main_call, pm_call = calls
    assert pm_call["is_postmortem"] is True
    assert pm_call["session_id"] == main_call["session_id"]
    assert pm_call["prompt_path"].name == "backward_postmortem.md"
    assert pm_call["kind"] == "backward"


def test_backward_wrapper_no_persist_when_no_postmortem_note(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the postmortem itself also times out (or returns no
    _progress.md), no draft is persisted — next dispatch cold-starts
    as it would have without F55. Best-effort design: no exception
    blocks the timeout flow."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        if kw.get("is_postmortem"):
            return 124  # postmortem also times out — no _progress.md
        return 124  # main + commit phase both time out
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-nodump")
    draft = _bw_drafts_path(tmp_path, gid)
    assert not draft.exists()




def test_backward_wrapper_clears_draft_on_goal_no_longer_open(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F55 review fix #2 — race-guard `goal_no_longer_open` means a
    sibling cascade already settled this goal; the in-flight PROPOSAL
    is moot. Clear the draft so a future re-decomposition (if the goal
    later reopens) doesn't get misled by stale carry-over."""
    gid = _seed_root_goal(tmp_path, conn)
    # Pre-seed a stale draft as if from a prior attempt
    draft = _bw_drafts_path(tmp_path, gid)
    draft.parent.mkdir(parents=True)
    draft.write_text("stale prior draft", encoding="utf-8")

    # Simulate a sibling having shelved the goal between dispatch and
    # post-spawn. We force this by mutating goal status before the
    # spawn returns.
    def fake_spawn_with_race(**kw):
        attempts = kw["attempts_dir"]
        # Phase 6 single-output: agent writes patch.lean with leading
        # comments + edits the F52 skeleton body. Add a sub-goal stub.
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        (attempts / "patch.lean").write_text(
            "-- s1: race test\n"
            + patch_text.replace(":= by sorry", ":= by trivial"),
            encoding="utf-8")
        import re
        m = re.search(r"theorem (s\d+)", patch_text)
        sid_token = m.group(1) if m else "s1"
        (attempts / f"new_sub_one.lean").write_text(
            "-- sub_one: race-test sub\n"
            "import Mathlib\nnamespace Problems.p\n"
            "theorem sub_one : True := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        # Race: between spawn return and the inner's status re-check
        # at the race guard, sibling shelved.
        db.update_goal_status(conn, gid, "shelved")
        conn.commit()
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn_with_race)
    monkeypatch.setattr(pipeline, "_lake_build_batch",
                        lambda ws, ts: (True, ""))

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-bw-race")
    assert r.outcome == "failed"
    assert r.failure_reason == "goal_no_longer_open"
    # Wrapper should have CLEARED the stale draft, not overwritten it
    # with the moot in-flight PROPOSAL.
    assert not draft.exists()


# ---------------------------------------------------------------------
# Phase 6.5 — Backward leaf-bypass salvage
# ---------------------------------------------------------------------

def test_backward_leaf_bypass_promotes_zero_subgoal_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Backward agent writes patch.lean with a complete proof body
    and no `new_*.lean` sub-goal stubs, framework registers a 0-subgoal
    strategy (mirroring `_try_promote_sorry_free` at the strategy level).
    Verify housekeeping picks it up next tick. Symmetric escape to
    Builder's `decline: too_hard` — agent saying 'this is leaf-able,
    not decompose-able' through behavior rather than directive."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        attempts = kw["attempts_dir"]
        # Edit F52 skeleton's body but emit no new_*.lean sub-goals.
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        patch_text = "-- main: trivial leaf proof\n" + patch_text.replace(
            ":= by sorry", ":= by trivial")
        (attempts / "patch.lean").write_text(patch_text, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build_batch",
                        lambda ws, ts: (True, ""))

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-leaf-bypass")
    assert r.outcome == "success"
    assert r.proposal_md.startswith("-- main: trivial leaf proof")

    # Strategy committed with scratch_path set, 0 strategy_subgoals rows.
    rows = conn.execute(
        "SELECT id, status, scratch_path, proposal_md FROM strategies "
        "WHERE goal_id = ?", (gid,)
    ).fetchall()
    assert len(rows) == 1
    s = rows[0]
    assert s["status"] == "proposed"
    assert s["scratch_path"].endswith(".lean")
    assert "trivial leaf proof" in s["proposal_md"]
    sub_count = conn.execute(
        "SELECT COUNT(*) FROM strategy_subgoals WHERE strategy_id = ?",
        (s["id"],),
    ).fetchone()[0]
    assert sub_count == 0
    # Ready for Verify: vacuously satisfies the no-unproved-subs gate.
    assert any(s2["id"] == s["id"]
               for s2 in db.strategies_ready_for_verify(conn))


def test_backward_no_subs_with_sorry_body_still_parse_proposal_fail(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Leaf-bypass requires a non-sorry body. Patch with `:= by sorry`
    and 0 sub-goals AND no decline directive is genuinely empty output —
    framework still rejects as parse_proposal_fail (the salvage triggers
    only when the agent over-delivered, not when they under-delivered)."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        attempts = kw["attempts_dir"]
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        # Add leading comment but leave body as sorry, no new_*.lean files.
        patch_text = "-- main: ...\n" + patch_text
        (attempts / "patch.lean").write_text(patch_text, encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", statement="True"),
        pipeline_id="pid-empty")
    # Phase 7 — parse_proposal_fail is retryable; helper exhausts budget.
    assert r.outcome == "exhausted"
    assert r.failure_reason == "parse_proposal_fail"
    assert "sorry body" in (r.failure_detail or "")
