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

from Tooling import agent, pipeline
from Tooling.state import db, manifest
from Tooling.llm.base import SpawnRC


@pytest.fixture(autouse=True)
def _intake_degraded(monkeypatch):
    """Formalizer intake is exercised by its own tests (test_intake.py);
    these tests pin the DEGRADED path (intake unusable -> classic cold
    flow, sid=None) so their spawn-order harnesses keep meaning."""
    from Tooling.pipeline import _intake
    monkeypatch.setattr(
        _intake, "run_intake",
        lambda **kw: _intake.IntakeOutcome(sid=None))




@pytest.fixture(autouse=True)
def _stub_verify_in_session(monkeypatch: pytest.MonkeyPatch):
    """Backward's commit verifies freshly-placed files on the pipeline's OWN
    session slot (`verify_in_session`), not by borrowing. File-scoped clean
    stub for these unit tests (no gateway running); tests exercising a
    rejection override it locally. Scoped here (not in the global conftest) so
    it can't shadow `test_gateway_lifecycle.py`'s real-function tests."""
    from Tooling.lsp import lifecycle as _gl

    def _stub(token, content, *, write_olean=False, axioms_for=None,
              decl_info=False, timeout=240.0, workspace=None,
              _retry_delays=None):
        return {
            "ok": True, "diagnostic_count": 0, "diagnostics": [],
            "olean_written": write_olean, "olean_path": None,
            "axioms": [] if axioms_for else None, "axiom_error": None,
            "decl_info": None, "decl_info_error": None,
        }
    monkeypatch.setattr(_gl, "verify_in_session", _stub)


def _seed_root_goal(tmp_path: Path, conn: sqlite3.Connection) -> int:
    problem = "p"
    pdir = tmp_path / "Problems" / problem
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n## Statement\nTrue\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
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


def _start_pipeline(conn: sqlite3.Connection, pid: str, gid: int) -> None:
    """v38 - play the dispatcher's dispatch-time INSERT so the retry
    helper's EAGER dead_attempts writes have their FK target."""
    db.record_pipeline_start(conn, pipeline_id=pid, kind="Formalizer",
                             target_id=str(gid), target_kind="Goal")


def test_first_dispatch_mints_session_id_and_passes_to_spawn(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First retry-loop iteration is cold: helper mints a fresh sid
    and passes it with is_retry=False / retry_context=None."""
    gid = _seed_root_goal(tmp_path, conn)
    _start_pipeline(conn, "pid-bw1", gid)
    captured = {}

    def fake_spawn(**kw):
        captured.update(kw)
        return 124  # bail out via timeout path; we only care about call args

    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-bw1",
    )
    assert captured["session_id"] is not None
    assert captured["is_retry"] is False
    assert captured["retry_context"] is None


def test_backward_quota_exhausted_deletes_strategy_row(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#101 — when the pipeline returns an infra failure (here:
    quota_exhausted rc=126), the strategy row reserved at the top of
    _run_backward_inner gets DELETEd rather than marked dead. The row
    was an empty shell — no proposal_md, no scratch, no sub-goal
    links — so leaving it around as 'dead' would be forensic noise."""
    gid = _seed_root_goal(tmp_path, conn)
    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: SpawnRC.QUOTA_EXHAUSTED)

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-bw-quota")
    assert r.outcome == "failed"
    assert r.failure_reason == "quota_exhausted"
    rows = conn.execute(
        "SELECT id FROM strategies WHERE goal_id=?", (gid,)
    ).fetchall()
    assert rows == [], (
        f"expected strategy row deleted on infra failure, got {len(rows)}"
    )


def test_backward_escaped_exception_deletes_orphan_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive try/finally — if `run_with_session_retries` raises
    (gateway crash, subprocess SIGKILL, internal pipeline bug), the
    strategy row reserved at the top of _run_backward_inner gets
    DELETEd before the exception propagates. Without this guard, the
    row sits forever at status='proposed' with empty proposal_md /
    scratch_path / no sub-goals (observed: s10488, s10505 on
    residue_thm 2026-05-20)."""
    gid = _seed_root_goal(tmp_path, conn)

    from Tooling.pipeline import _retry as _retry_mod

    def boom(**kw):
        raise RuntimeError("simulated worker crash mid-spawn")

    monkeypatch.setattr(_retry_mod, "run_with_session_retries", boom)

    with pytest.raises(RuntimeError, match="simulated worker crash"):
        pipeline.run_backward(
            conn, goal_id=gid, workspace=tmp_path,
            mfst=manifest.Manifest(problem="p", body="True"),
            pipeline_id="pid-bw-crash")

    rows = conn.execute(
        "SELECT id, status, proposal_md, scratch_path"
        " FROM strategies WHERE goal_id=?", (gid,)
    ).fetchall()
    assert rows == [], (
        f"expected orphan strategy row deleted on escaped exception, "
        f"got {[dict(r) for r in rows]}"
    )


def test_backward_escaped_exception_keeps_committed_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """try/finally only deletes the row when it's still in the empty
    placeholder state (no proposal_md, no scratch_path). If a prior
    in-pipeline retry already committed the strategy and a later phase
    raised, the committed work must NOT be wiped."""
    gid = _seed_root_goal(tmp_path, conn)
    rel = db.get_goal(conn, gid)["lean_path"]

    from Tooling.pipeline import _retry as _retry_mod

    captured_sid = {"sid": None}

    def fake_run(**kw):
        # Find the most-recently inserted strategy row (the one just
        # reserved by _run_backward_inner) and fill it in to mimic a
        # successful commit phase. Then raise to simulate a downstream
        # crash AFTER the row is no longer a placeholder.
        row = conn.execute(
            "SELECT id FROM strategies WHERE goal_id=?"
            " ORDER BY id DESC LIMIT 1", (gid,)
        ).fetchone()
        sid = int(row["id"])
        captured_sid["sid"] = sid
        conn.execute(
            "UPDATE strategies SET proposal_md='committed work',"
            " scratch_path='Problems/p/proofs/_strategy_s.lean'"
            " WHERE id=?", (sid,)
        )
        conn.commit()
        raise RuntimeError("crash after commit")

    monkeypatch.setattr(_retry_mod, "run_with_session_retries", fake_run)

    with pytest.raises(RuntimeError, match="crash after commit"):
        pipeline.run_backward(
            conn, goal_id=gid, workspace=tmp_path,
            mfst=manifest.Manifest(problem="p", body="True"),
            pipeline_id="pid-bw-commit-then-crash")

    # Committed row survives — outer dispatcher will record the
    # pipeline failure and the row stays at 'proposed' as a real
    # forensic artifact (NOT a placeholder orphan).
    rows = conn.execute(
        "SELECT id, status, proposal_md FROM strategies WHERE goal_id=?",
        (gid,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == captured_sid["sid"]
    assert rows[0]["proposal_md"] == "committed work"


def test_backward_agent_failure_keeps_strategy_dead(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#101 — agent-side failures (parse error, decline, sorry stub
    persistence, signature mismatch) keep the strategy row as 'dead'
    for forensic review. Only infra reasons trigger DELETE."""
    gid = _seed_root_goal(tmp_path, conn)
    _start_pipeline(conn, "pid-bw-agent-fail", gid)
    # Watchdog STUCK_THINKING for cold spawn AND fresh-rescue stage 2
    # AND postmortem → entire flow exhausts attempts and bails with
    # an agent-side failure_reason (not in _INFRA_REASONS).
    monkeypatch.setattr(agent, "spawn_llm",
                        lambda **kw: SpawnRC.STUCK_THINKING)
    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-bw-agent-fail")
    assert r.outcome != "success"
    rows = conn.execute(
        "SELECT id, status FROM strategies WHERE goal_id=?", (gid,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "dead", (
        f"agent-side failure should leave strategy as 'dead', "
        f"got {rows[0]['status']!r}; "
        f"failure_reason={r.failure_reason!r}"
    )


def test_backward_moot_deletes_empty_strategy_row(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`moot` = the agent NEVER ran (retry pre-loop budget<=0 because the
    goal is already over SHELVE_THRESHOLD). run_backward reserves a strategy
    row BEFORE the retry helper, so the moot leaves it behind — an empty
    shell with no forensic value, like an infra death. It must be DELETED,
    not marked 'dead'. Regression: the P13 4284 wedge moot-spin piled up
    5458 empty dead strategies on ONE goal because `moot` fell into the
    mark-dead branch (BFS re-dispatched Backward on the over-budget goal
    thousands of times, each reserving a row then retry-mooting) (2026-06-15)."""
    from Tooling.core import dispatcher
    gid = _seed_root_goal(tmp_path, conn)
    # Push the goal over SHELVE_THRESHOLD so the retry helper pre-loop moots
    # (budget = SHELVE_THRESHOLD - attempts <= 0) without ever spawning.
    conn.execute("UPDATE goals SET attempts=? WHERE id=?",
                 (dispatcher.SHELVE_THRESHOLD + 2, gid))
    conn.commit()
    spawned = {"n": 0}

    def fake_spawn(**kw):
        spawned["n"] += 1
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-bw-moot")
    assert r.outcome == "moot"
    assert spawned["n"] == 0, "pre-loop moot must not spawn an agent"
    rows = conn.execute(
        "SELECT id, status FROM strategies WHERE goal_id=?", (gid,)
    ).fetchall()
    assert rows == [], (
        f"moot (agent never ran) must DELETE the empty reserved strategy, "
        f"not mark it 'dead'; got {[dict(r) for r in rows]}")


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
    _start_pipeline(conn, "pid-bw-cold", gid)
    rel = db.get_goal(conn, gid)["lean_path"]
    stale_sid = db.insert_strategy(
        conn, goal_id=gid, lean_path=rel,
        created_by="pid-old", proposal_md="", scratch_path="",
    )
    db.update_strategy_status(conn, stale_sid, "dead")

    monkeypatch.setattr(agent, "spawn_llm", lambda **kw: 124)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
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
    _start_pipeline(conn, "pid-bw-timeout", gid)

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
        mfst=manifest.Manifest(problem="p", body="True"),
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
    _start_pipeline(conn, "pid-bw-pm-args", gid)
    calls = []

    def fake_spawn(**kw):
        calls.append(kw)
        if kw.get("is_postmortem"):
            return 124  # don't bother writing — just inspect args
        return 124  # main timeout
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
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
    _start_pipeline(conn, "pid-bw-nodump", gid)

    def fake_spawn(**kw):
        if kw.get("is_postmortem"):
            return 124  # postmortem also times out — no _progress.md
        return 124  # main + commit phase both time out
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-bw-nodump")
    draft = _bw_drafts_path(tmp_path, gid)
    assert not draft.exists()


def test_backward_fresh_rescue_stage2_bail_via_progress_md_persists_draft(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward bail via two-stage fresh-rescue (2026-05-10): main
    spawn is watchdog-killed (rc=128 STUCK_THINKING), retry helper
    runs stage 2 (fresh sid + ship-or-bail prompt). The stage-2
    agent decides bail: writes `_progress.md` and leaves patch.lean
    as the cold-start skeleton. Backward parse's strict bail
    discriminator (no leading + no new_*.lean + sorry body +
    _progress.md present) triggers `agent_bailed`. Outer wrapper
    persists `_progress.md` into `.drafts/backward_g<id>.md` so the
    next cold dispatch reads it via Context.md."""
    gid = _seed_root_goal(tmp_path, conn)
    spawn_calls: list[dict] = []

    def fake_spawn(**kw):
        spawn_calls.append(kw)
        # Iter 0 main: stuck. Stage 2: writes _progress.md (bail).
        if kw.get("inline_prompt"):
            (kw["attempts_dir"] / "_progress.md").write_text(
                "Tried Kelly minimiser shape with 3 sub-lemmas; could "
                "not name the perpendicular-distance lemma. Direction "
                "may need switching to a contradiction proof on "
                "min-distance triple.",
                encoding="utf-8")
            return SpawnRC.OK
        return SpawnRC.STUCK_THINKING
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-bw-bail")
    assert r.failure_reason == "agent_bailed"
    # Outer wrapper persists _progress.md to .drafts/ (non-success path).
    draft = _bw_drafts_path(tmp_path, gid)
    assert draft.exists()
    body = draft.read_text(encoding="utf-8")
    assert "Kelly minimiser" in body
    assert "perpendicular-distance" in body
    # 2 spawn invocations: main (stuck) + stage 2 fresh (bail).
    assert len(spawn_calls) == 2
    assert spawn_calls[0].get("inline_prompt") in (None,)
    assert spawn_calls[1]["inline_prompt"] is not None
    # Stage 2 uses a different sid than the broken main.
    assert spawn_calls[1]["session_id"] != spawn_calls[0]["session_id"]


def test_backward_progress_md_with_real_split_does_not_trigger_bail(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bail discriminator must require an empty patch.lean skeleton
    (no leading + sorry body) AND no new_*.lean files. SG run #6 g266
    pattern: cold-spawn agent finished a valid split (real patch.lean
    leading + new_<slug>.lean stub) AND ALSO wrote _progress.md as a
    cargo-cult bonus before subprocess timeout. The strict
    discriminator must NOT route this to agent_bailed — losing valid
    work to a false-positive bail would be worse than the original
    discard-on-timeout bug we just fixed."""
    gid = _seed_root_goal(tmp_path, conn)

    def fake_spawn(**kw):
        attempts = kw["attempts_dir"]
        # Replicate the agent's three writes (matches g266 timeline):
        # patch.lean with leading + body, new_<slug>.lean stub, then
        # _progress.md as bonus note.
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        # Add leading comment + change body away from sorry stub.
        (attempts / "patch.lean").write_text(
            "-- s_one: real Kelly minimiser sketch\n"
            + patch_text.replace(":= by sorry", ":= by exact sub_one"),
            encoding="utf-8")
        (attempts / "new_sub_one.lean").write_text(
            "-- sub_one: real sub-lemma\n"
            "import Mathlib\nnamespace Problems.p\n"
            # NOT `True`: the root goal in this fixture IS `True`, so a
            # `True` sub-goal restates its own parent verbatim — dedupe
            # tier-0 now rejects that as circular (correctly; the probe
            # blindness is what let this fixture through before). This
            # test is about the `_progress.md` bail discriminator, so the
            # split has to be a REAL one.
            "theorem sub_one : 0 = 0 := by sorry\n"
            "end Problems.p\n",
            encoding="utf-8")
        (attempts / "_progress.md").write_text(
            "## Progress note for next spawn\n"
            "Status: validate_file passed; files written; no blocker.\n",
            encoding="utf-8")
        return SpawnRC.OK
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)
    monkeypatch.setattr(pipeline, "_lake_build_batch",
                        lambda ws, ts: (True, ""))

    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-bw-no-false-bail")
    # Discriminator passed — parse continues and treats this as a real
    # decomposition commit (or whatever downstream parse decides).
    # Critical: NOT agent_bailed.
    assert r.failure_reason != "agent_bailed", (
        f"strict bail discriminator failed: real split + _progress.md "
        f"was misclassified as bail. outcome={r.outcome}, "
        f"reason={r.failure_reason}, detail={r.failure_detail}")


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
            # NOT `True`: the root goal in this fixture IS `True`, so a
            # `True` sub-goal restates its own parent verbatim — dedupe
            # tier-0 now rejects that as circular (correctly; the probe
            # blindness is what let this fixture through before). This
            # test is about the `_progress.md` bail discriminator, so the
            # split has to be a REAL one.
            "theorem sub_one : 0 = 0 := by sorry\n"
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
        mfst=manifest.Manifest(problem="p", body="True"),
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
        mfst=manifest.Manifest(problem="p", body="True"),
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


def test_backward_leaf_bypass_axiom_violation_rejects_at_acceptance(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Acceptance-gate axiom probe (option (a)): when Backward agent
    ships a leaf-bypass patch whose elaborate succeeds (LSP reports
    0 errors) but whose `#print axioms` exposes sorryAx, framework
    rejects at the acceptance gate — strategy is NEVER promoted to
    ready_for_verify, scratch file is unlinked, helper buffers
    axiom_violation as a retryable failure (analogous to
    lake_build_error)."""
    gid = _seed_root_goal(tmp_path, conn)
    # v38 — the dispatch-time pipelines row must exist for the helper's
    # eager dead_attempts writes (FK).
    db.record_pipeline_start(
        conn, pipeline_id="pid-leaf-bypass-axiom-violation",
        kind="Formalizer", target_id=str(gid), target_kind="Goal")
    from Tooling.lsp import lifecycle as _gl
    # Backward's leaf-bypass verifies on the pipeline's OWN session slot
    # (verify_in_session); override it to surface a sorryAx-tainted elaborate.
    def _stub_verify_with_sorry_ax(token, content, *, write_olean=False,
                                    axioms_for=None, decl_info=False,
                                    timeout=240.0,
                                    workspace=None, _retry_delays=None):
        return {
            "ok": True, "diagnostic_count": 0, "diagnostics": [],
            "olean_written": write_olean, "olean_path": None,
            "axioms": ["sorryAx"] if axioms_for else None,
            "axiom_error": None,
            "decl_info": None, "decl_info_error": None,
        }
    monkeypatch.setattr(_gl, "verify_in_session", _stub_verify_with_sorry_ax)

    def fake_spawn(**kw):
        attempts = kw["attempts_dir"]
        patch_text = (attempts / "patch.lean").read_text(encoding="utf-8")
        (attempts / "patch.lean").write_text(
            "-- main: leaf-bypass shipping a sorry-tainted body\n"
            + patch_text.replace(":= by sorry", ":= by trivial"),
            encoding="utf-8")
        return 0
    monkeypatch.setattr(agent, "spawn_llm", fake_spawn)

    mfst = manifest.Manifest(problem="p", body="True",
                              axioms_whitelist=["propext"])
    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=mfst, pipeline_id="pid-leaf-bypass-axiom-violation")

    # axiom_violation is RETRYABLE (unlike agent_infeasible / agent_
    # declined which are terminal): helper records (eagerly, v38) +
    # retries; with fake_spawn always shipping the same sorry-tainted
    # patch, the helper exhausts budget. Every recorded failure is
    # axiom_violation.
    assert r.outcome == "exhausted"
    assert r.failure_reason == "axiom_violation"
    assert "sorryAx" in r.failure_detail
    da = conn.execute(
        "SELECT failure_reason FROM dead_attempts WHERE pipeline_id=?",
        ("pid-leaf-bypass-axiom-violation",)).fetchall()
    assert len(da) >= 2, (
        f"expected helper to retry on axiom_violation; got "
        f"{len(da)} recorded failure(s)"
    )
    assert all(row["failure_reason"] == "axiom_violation" for row in da)
    # Strategy never promoted (scratch_path stays empty).
    rows = conn.execute(
        "SELECT scratch_path FROM strategies WHERE goal_id=?",
        (gid,)).fetchall()
    assert all(r_["scratch_path"] == "" for r_ in rows), (
        "leaf-bypass scratch_path must stay empty when axiom probe "
        "rejects at acceptance gate (no promote_to_alias attempted)"
    )
    # All scratch files unlinked
    proofs_dir = tmp_path / "Problems" / "p" / "proofs"
    if proofs_dir.exists():
        leftover = list(proofs_dir.glob("_strategy_*.lean"))
        assert not leftover, (
            f"leaf-bypass scratch files must be unlinked on axiom "
            f"rejection; found {leftover}"
        )


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

    _start_pipeline(conn, "pid-empty", gid)
    r = pipeline.run_backward(
        conn, goal_id=gid, workspace=tmp_path,
        mfst=manifest.Manifest(problem="p", body="True"),
        pipeline_id="pid-empty")
    # Phase 7 — parse_proposal_fail is retryable; helper exhausts budget.
    assert r.outcome == "exhausted"
    assert r.failure_reason == "parse_proposal_fail"
    assert "sorry body" in (r.failure_detail or "")
