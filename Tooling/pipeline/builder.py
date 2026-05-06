"""Builder pipeline. Phase 1 deterministic tactic_try via Mathlib `hint`,
Phase 2 LLM patch with F33 same-session retry, F46 spawn-fast-fail
handling, F48 decline channel, F55 partial-output persistence.

Public entry point: `run_builder`. Shared helpers (`_grep_forbidden`,
`_is_sorry_stub`, `_replace_proof_body`, `_attempt_postmortem`,
`_spawn_failure`, `_safe_glob`, `PipelineResult`, `PROMPT_DIR`,
`_parse_hint_winner`, `_lake_build`, `DECLINE_*`, `_parse_decline_reason`,
`_drafts`) are imported from the package root.
"""
from __future__ import annotations

import shutil
import sqlite3
import time
import uuid
from pathlib import Path

from .. import agent, db, diagnostics, manifest
from ..llm.base import SpawnRC


def _fetch_last_builder_error(conn: sqlite3.Connection,
                              goal_id: int) -> str:
    """F33 — return the smart-truncated lake error from this goal's
    most recent Builder dead_attempt. Used as `retry_context` inlined
    into the retry prompt (no separate file needed — agent sees the
    error immediately, no Read tool round-trip)."""
    row = conn.execute(
        "SELECT da.failure_detail FROM dead_attempts da"
        " JOIN pipelines p ON p.id = da.pipeline_id"
        " WHERE da.target_id = ? AND da.target_kind = 'Goal'"
        "   AND p.kind = 'Builder'"
        " ORDER BY da.id DESC LIMIT 1",
        (goal_id,),
    ).fetchone()
    if row is None or not row["failure_detail"]:
        return ""
    return diagnostics.strip_lake_noise(row["failure_detail"])


def run_builder(conn: sqlite3.Connection, *, goal_id: int,
                workspace: Path, mfst: manifest.Manifest,
                pipeline_id: str) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner pipeline then persists or clears
    the partial-output draft (F55) so a future spawn on this same goal
    sees the in-flight patch from the prior failed attempt instead of
    starting from scratch.

    Outcomes:
      - `proved`: success — clear any draft (no carry-over wanted).
      - anything else (rc!=0 from spawn, lake_build_error, ...):
        persist whatever the spawn wrote so the next dispatch picks
        up from a sketch.
    """
    from . import (  # late import to avoid circular package init
        PipelineResult, _drafts,
    )
    goal_row = db.get_goal(conn, goal_id)
    if goal_row is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")
    problem_dir = workspace / "Problems" / goal_row["problem"]
    result = _run_builder_inner(conn, goal_id=goal_id, workspace=workspace,
                                mfst=mfst, pipeline_id=pipeline_id)
    if result.outcome == "proved":
        _drafts.clear_partial(problem_dir=problem_dir, kind="builder",
                              goal_id=goal_id)
    else:
        attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
        _drafts.persist_partials(attempts_dir=attempts_dir,
                                 problem_dir=problem_dir,
                                 kind="builder", goal_id=goal_id)
    return result


def _run_builder_inner(conn: sqlite3.Connection, *, goal_id: int,
                       workspace: Path, mfst: manifest.Manifest,
                       pipeline_id: str) -> "PipelineResult":  # noqa: F821
    from . import (
        PipelineResult, PROMPT_DIR,
        _attempt_postmortem, _grep_forbidden, _is_sorry_stub,
        _lake_build, _parse_decline_reason, _parse_hint_winner,
        _replace_proof_body, _safe_glob, _spawn_failure,
        DECLINE_PARENT_TYPE_INFEASIBLE,
    )

    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")

    goal_lean = workspace / goal["lean_path"]
    if not goal_lean.exists():
        return PipelineResult(
            outcome="failed", failure_reason="lean_file_missing",
            failure_detail=str(goal_lean),
        )
    source = goal_lean.read_text(encoding="utf-8")

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)

    # Phase 1: tactic_try via Mathlib `hint` — only on fresh `:= by sorry`
    # stubs (skips post-Backward structured patches), and only on the
    # first dispatch (attempts == 0) since `hint`'s register_hint set is
    # deterministic — re-running on later dispatches wastes a lake build.
    #
    # Two-build flow:
    #   (1) probe: `:= by hint` — Lean elaborates all `register_hint`
    #       tactics; emits `info: ... Try these: [apply] 🎉️ <tac>`
    #       lines for each that closed the goal. Failure → "error: No
    #       suggestions available" (rc != 0).
    #   (2) confirm: rewrite as `:= by <winner>` and rebuild. The
    #       artifact ends up with the precise tactic, not `hint`
    #       (forensic clarity + avoids silent `admitGoal` fall-through
    #       if the registered set changes). Cheap — second build hits
    #       warm cache.
    #
    # Any failure in this block (probe build, no winner, confirm rebuild)
    # restores the backup and falls through to Phase 2 in the SAME
    # dispatch — Phase 1 doesn't terminate the pipeline early.
    # See pipeline/__init__.py `_HINT_WINNER_RE` for the parser.
    if goal["attempts"] == 0 and _is_sorry_stub(source):
        backup_text = source

        probe_text = _replace_proof_body(source, "hint")
        goal_lean.write_text(probe_text, encoding="utf-8")
        ok, probe_out = _lake_build(workspace, goal_lean)
        winner = _parse_hint_winner(probe_out) if ok else None

        if winner is not None:
            # Confirm — rewrite with the precise winning tactic and rebuild.
            # `hint` runs in a shared mctx; isolated re-elaboration of
            # just the winner can theoretically diverge (rare).
            final_text = _replace_proof_body(source, winner)
            goal_lean.write_text(final_text, encoding="utf-8")
            ok, _ = _lake_build(workspace, goal_lean)
            if ok:
                forbidden = _grep_forbidden(final_text, mfst.forbidden_lemmas)
                if forbidden:
                    goal_lean.write_text(backup_text, encoding="utf-8")
                    return PipelineResult(outcome="failed",
                                          failure_reason="forbidden_lemma",
                                          failure_detail=forbidden)
                # Forensic snapshot. Filename is fixed (`won_hint.lean`)
                # since the winning tactic may contain spaces / quotes /
                # unicode unfit for filenames; the file body has the
                # exact tactic in `:= by <winner>`.
                (attempts_dir / "won_hint.lean").write_text(
                    final_text, encoding="utf-8"
                )
                return PipelineResult(outcome="proved")

        # Phase 1 didn't close the goal — restore the original sorry-stub
        # and fall through to Phase 2 LLM.
        goal_lean.write_text(backup_text, encoding="utf-8")

    # Phase 2: tactic_llm with F33 same-session retry.
    # First attempt mints a session id and pins it via --session-id;
    # subsequent attempts reuse via --resume + a short RETRY_NOTE.md
    # that relies on the prior turn living in claude's session memory.
    sid = db.get_builder_session_id(conn, goal_id)
    is_retry = sid is not None
    retry_context: str | None = None
    if not is_retry:
        # P1-#7: mint UUID locally; persist AFTER spawn returns so a
        # process kill mid-spawn leaves DB session_id NULL instead of
        # pointing at a session claude never minted (which would cost
        # one wasted --resume / rc=125 cycle on the next dispatch).
        sid = str(uuid.uuid4())
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir, kind="builder")
    else:
        retry_context = _fetch_last_builder_error(conn, goal_id)

    spawn_t0 = time.monotonic()
    rc = agent.spawn_llm(
        kind="builder",
        prompt_path=PROMPT_DIR / "builder.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
        session_id=sid,
        is_retry=is_retry,
        retry_context=retry_context,
    )
    spawn_dur = time.monotonic() - spawn_t0

    # P1-#7: persist session_id only after we know spawn completed
    # past the kill window. rc 124/125 paths below clear/replace
    # explicitly; for any other return code claude minted the
    # session and a future retry's --resume can leverage it.
    if not is_retry and rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
        db.set_builder_session_id(conn, goal_id, sid)

    # F33 — fallback for stale session (claude's on-disk session was
    # GC'd or the daemon's DB id outlived the file). One-time retry
    # with a fresh uuid down the cold path.
    if rc == SpawnRC.STALE_SESSION:
        db.set_builder_session_id(conn, goal_id, None)
        sid = str(uuid.uuid4())
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir, kind="builder")
        spawn_t0 = time.monotonic()
        rc = agent.spawn_llm(
            kind="builder",
            prompt_path=PROMPT_DIR / "builder.md",
            problem_dir=workspace / "Problems" / goal["problem"],
            attempts_dir=attempts_dir,
            session_id=sid,
            is_retry=False,
        )
        spawn_dur = time.monotonic() - spawn_t0
        if rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
            db.set_builder_session_id(conn, goal_id, sid)

    if rc == SpawnRC.TIMEOUT:
        # Timeout: agent SIGKILL'd mid-write. F55 — before clearing the
        # session id, do a short postmortem spawn that resumes the same
        # session and asks the agent to dump state + blockers into
        # `_progress.md`. The wrapper then captures _progress.md as
        # the partial draft for the next dispatch.
        if sid is not None:
            _attempt_postmortem(
                kind="builder",
                prompt_path=PROMPT_DIR / "builder_postmortem.md",
                problem_dir=workspace / "Problems" / goal["problem"],
                attempts_dir=attempts_dir,
                session_id=sid,
            )
        db.set_builder_session_id(conn, goal_id, None)
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return PipelineResult(outcome="failed",
                              failure_reason=reason,
                              failure_detail=detail)
    if rc != 0:
        # Ordinary failure: keep session_id so next attempt's --resume
        # has the prior failed-turn context to learn from. (Gemini /
        # OpenAI providers ignore session_id — clearing on rc=124 only.)
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return PipelineResult(outcome="failed",
                              failure_reason=reason,
                              failure_detail=detail)

    proposal = (attempts_dir / "PROPOSAL.md")
    proposal_text = proposal.read_text(encoding="utf-8") if proposal.exists() else ""

    patches = _safe_glob(attempts_dir, "patch*.lean")
    if not patches:
        # F48 — Builder decline channel. The agent followed builder.md's
        # "When to skip writing a patch" hatch: it produced a non-empty
        # PROPOSAL.md explaining why the goal is too hard / needs
        # decomposition, but did not write patch.lean. Cascade treats
        # this distinctly from agent_no_output (no PROPOSAL either).
        #
        # `decline_reason` frontmatter sub-routes:
        #   - `parent_type_infeasible` → agent_infeasible (cascade-up:
        #     parent strategy dies, parent goal re-decomposes)
        #   - `too_hard` / missing      → agent_declined  (jump this
        #     goal to Backward via F48 path)
        if proposal_text.strip():
            reason = _parse_decline_reason(proposal_text)
            if reason == DECLINE_PARENT_TYPE_INFEASIBLE:
                return PipelineResult(
                    outcome="failed",
                    failure_reason="agent_infeasible",
                    failure_detail=("builder reports parent type infeasible; "
                                    "PROPOSAL.md must include counterexample"),
                    proposal_md=proposal_text,
                )
            return PipelineResult(
                outcome="failed", failure_reason="agent_declined",
                failure_detail="builder declined; PROPOSAL.md explains why",
                proposal_md=proposal_text,
            )
        return PipelineResult(outcome="failed", failure_reason="agent_no_output",
                              failure_detail="no patch*.lean", proposal_md=proposal_text)
    patch = patches[0]
    patch_text = patch.read_text(encoding="utf-8")

    forbidden = _grep_forbidden(patch_text, mfst.forbidden_lemmas)
    if forbidden:
        return PipelineResult(
            outcome="failed", failure_reason="forbidden_lemma",
            failure_detail=forbidden, proposal_md=proposal_text,
        )

    # Stage: copy patch over goal lean (backup first)
    backup = goal_lean.with_suffix(goal_lean.suffix + ".backup")
    shutil.copy2(goal_lean, backup)
    shutil.copy2(patch, goal_lean)
    ok, err = _lake_build(workspace, goal_lean)
    if ok:
        backup.unlink()
        return PipelineResult(outcome="proved")
    shutil.copy2(backup, goal_lean)
    backup.unlink()
    return PipelineResult(
        outcome="failed", failure_reason="lake_build_error",
        failure_detail=diagnostics.annotate_failure_detail(err),
        proposal_md=proposal_text,
    )
