"""Builder pipeline. Phase 1 deterministic tactic_try via Mathlib `hint`,
Phase 2 LLM patch via in-pipeline retry helper (Phase 7).

Phase 6 single-output: agent emits patch.lean with leading `--`
annotation block (no separate PROPOSAL.md); declines via
`-- decline: <reason>` directive at the file head.

Phase 7 in-pipeline retry: Phase 2 delegates to
`run_with_session_retries` which owns budget computation, sid lifecycle,
per-spawn forensic + attempts++. claude session memory is shared
across in-pipeline retry iterations via `claude --resume <sid>`; sid
is a local var in the helper, not persisted to DB.

Public entry point: `run_builder`.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from .. import agent, db, diagnostics, manifest


def run_builder(conn: sqlite3.Connection, *, goal_id: int,
                workspace: Path, mfst: manifest.Manifest,
                pipeline_id: str) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner pipeline then persists or clears
    the partial-output draft (F55) so a future spawn on this same goal
    sees the in-flight patch from the prior failed attempt instead of
    starting from scratch.

    Outcomes:
      - `proved`: success — clear any draft (no carry-over wanted).
      - `moot`: goal terminated by parallel cascade → no useful draft.
      - anything else (failed / exhausted): persist whatever the spawn
        wrote so the next dispatch picks up from a sketch.
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
    if result.outcome in ("proved", "moot"):
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
        _attempt_postmortem, _extract_decline_reason,
        _extract_leading_comments, _grep_forbidden, _is_sorry_stub,
        _lake_build, _parse_hint_winner, _replace_proof_body,
        _safe_glob,
        DECLINE_PARENT_TYPE_INFEASIBLE,
    )
    from ._retry import SpawnCtx, run_with_session_retries
    from .. import dispatcher  # late: BUILDER_THRESHOLD live value

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
    problem_dir = workspace / "Problems" / goal["problem"]

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
    if goal["attempts"] == 0 and _is_sorry_stub(source):
        backup_text = source

        probe_text = _replace_proof_body(source, "hint")
        goal_lean.write_text(probe_text, encoding="utf-8")
        ok, probe_out = _lake_build(workspace, goal_lean)
        winner = _parse_hint_winner(probe_out) if ok else None

        if winner is not None:
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
                # exact tactic in `:= by <winner>`. No annotation written —
                # `by <winner>` (linarith / decide / simp ...) is short
                # enough to self-document; a synthetic comment would be
                # mechanical noise.
                (attempts_dir / "won_hint.lean").write_text(
                    final_text, encoding="utf-8"
                )
                return PipelineResult(outcome="proved")

        # Phase 1 didn't close the goal — restore the original sorry-stub
        # and fall through to Phase 2 LLM.
        goal_lean.write_text(backup_text, encoding="utf-8")

    # Phase 2: tactic_llm via in-pipeline retry helper.
    # Helper owns budget = BUILDER_THRESHOLD - goal.attempts (decision 1),
    # sid lifecycle (cold first, --resume thereafter), per-retry
    # forensic. Builder-specific spawn / parse / postmortem are closures
    # over the pipeline scope below.

    def builder_spawn(ctx: SpawnCtx) -> int:
        # Cold start: fresh Context.md compile (snapshot Manifest +
        # goal history at this exact attempt). Warm: skip — agent's
        # session memory carries the Context from the prior call;
        # retry_context inlines the prior lake error.
        if ctx.cold:
            agent.compile_context(conn, goal=goal, mfst=mfst,
                                  attempts_dir=ctx.attempts_dir,
                                  kind="builder")
        return agent.spawn_llm(
            kind="builder",
            prompt_path=PROMPT_DIR / "builder.md",
            problem_dir=problem_dir,
            attempts_dir=ctx.attempts_dir,
            session_id=ctx.sid,
            is_retry=not ctx.cold,
            retry_context=ctx.retry_context,
        )

    def builder_parse() -> "PipelineResult":  # noqa: F821
        patches = _safe_glob(attempts_dir, "patch*.lean")
        if not patches:
            return PipelineResult(
                outcome="failed", failure_reason="agent_no_output",
                failure_detail="no patch*.lean",
            )
        patch = patches[0]
        patch_text = patch.read_text(encoding="utf-8")

        # Phase 6 single-output: agent's metadata lives in patch.lean's
        # leading comment block. `-- decline: <reason>` directive routes
        # to the agent_declined / agent_infeasible terminal branches;
        # otherwise the block is the goal's annotation source.
        leading = _extract_leading_comments(patch_text)
        decline = _extract_decline_reason(leading)
        if decline == DECLINE_PARENT_TYPE_INFEASIBLE:
            return PipelineResult(
                outcome="failed",
                failure_reason="agent_infeasible",
                failure_detail=("builder reports parent type infeasible; "
                                "leading comments must include counterexample"),
                proposal_md=leading,
            )
        if decline is not None:
            # Any other declared decline reason maps to agent_declined
            # (jump to Backward). `too_hard` is the canonical value;
            # unknown sub-reasons stay routed here defensively.
            return PipelineResult(
                outcome="failed", failure_reason="agent_declined",
                failure_detail=f"builder declined: {decline}",
                proposal_md=leading,
            )

        forbidden = _grep_forbidden(patch_text, mfst.forbidden_lemmas)
        if forbidden:
            return PipelineResult(
                outcome="failed", failure_reason="forbidden_lemma",
                failure_detail=forbidden, proposal_md=leading,
            )

        # Stage: copy patch over goal lean (backup first)
        backup = goal_lean.with_suffix(goal_lean.suffix + ".backup")
        shutil.copy2(goal_lean, backup)
        shutil.copy2(patch, goal_lean)
        ok, err = _lake_build(workspace, goal_lean)
        if ok:
            # Annotation is a hard success condition: an empty leading-
            # comment block means the agent skipped documentation. Roll
            # back to the sorry-stub backup and retry. The agent's patch
            # already contains the annotation in place, so on success we
            # just keep the file as the proved goal source verbatim.
            if not leading.strip():
                shutil.copy2(backup, goal_lean)
                backup.unlink()
                return PipelineResult(
                    outcome="failed",
                    failure_reason="agent_no_annotation",
                    failure_detail="patch built but had no leading comment block",
                )
            backup.unlink()
            return PipelineResult(outcome="proved", proposal_md=leading)
        shutil.copy2(backup, goal_lean)
        backup.unlink()
        return PipelineResult(
            outcome="failed", failure_reason="lake_build_error",
            failure_detail=diagnostics.annotate_failure_detail(err),
            proposal_md=leading,
        )

    def builder_postmortem(sid: str) -> None:
        _attempt_postmortem(
            kind="builder",
            prompt_path=PROMPT_DIR / "builder_postmortem.md",
            problem_dir=problem_dir,
            attempts_dir=attempts_dir,
            session_id=sid,
        )

    def builder_reflection(sid: str, result) -> None:
        from ._reflection import attempt_reflection
        from .. import config
        cap = config.get(
            "lessons.cap", default=10, cast=int, workspace=workspace,
        )
        attempt_reflection(
            kind="builder",
            sid=sid,
            slug=goal["slug"],
            outcome=(result.failure_reason
                     if result.failure_reason
                     else result.outcome),
            problem_dir=problem_dir,
            attempts_dir=attempts_dir,
            lessons_cap=int(cap),
            prompt_dir=PROMPT_DIR,
        )

    return run_with_session_retries(
        conn=conn,
        goal_id=goal_id,
        pipeline_id=pipeline_id,
        budget_threshold=dispatcher.BUILDER_THRESHOLD,
        shelve_threshold=dispatcher.SHELVE_THRESHOLD,
        attempts_dir=attempts_dir,
        spawn_fn=builder_spawn,
        parse_fn=builder_parse,
        postmortem_fn=builder_postmortem,
        workspace=workspace,
        reflection_fn=builder_reflection,
    )
