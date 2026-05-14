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

LSP-backed agent: Builder spawns claude with an `--mcp-config`
pointing at the long-living `Tooling.lsp_gateway` HTTP server. The
agent gets apply_edit / goal_at / errors_at tools that operate on
`goal_lean` directly. Final patch.lean output protocol unchanged.

Public entry point: `run_builder`.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from .. import agent, context, db, diagnostics, manifest


def run_builder(conn: sqlite3.Connection, *, goal_id: int,
                workspace: Path, mfst: manifest.Manifest,
                pipeline_id: str) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner pipeline then persists or clears
    the partial-output draft so a future spawn on this same goal
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
    problem_dir = db.problem_dir(workspace, goal_row["problem"])
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
        _parse_hint_winner, _replace_proof_body,
        _safe_glob, _write_mcp_config,
        DECLINE_TO_FAILURE_REASON,
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
    problem_dir = db.problem_dir(workspace, goal["problem"])

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
        from .. import gateway_lifecycle

        # Probe: `:= by hint` elaborates all `register_hint` tactics;
        # the `hint` tactic emits info diagnostics with a "Try these:
        # [apply] 🎉️ <tac>" block when it found a closer. We scan all
        # info diagnostics' message text for the marker. write_olean
        # is skipped (probe is throwaway).
        probe_text = _replace_proof_body(source, "hint")
        goal_lean.write_text(probe_text, encoding="utf-8")
        v_probe = gateway_lifecycle.verify_file(
            goal_lean, write_olean=False, workspace=workspace,
        )
        winner: str | None = None
        if "error" not in v_probe and v_probe.get("ok"):
            for d in v_probe.get("diagnostics") or []:
                if d.get("severity") == "info":
                    w = _parse_hint_winner(d.get("message", ""))
                    if w:
                        winner = w
                        break

        if winner is not None:
            final_text = _replace_proof_body(source, winner)
            goal_lean.write_text(final_text, encoding="utf-8")
            fq_name = f"Problems.{goal['problem']}.{goal['slug']}"
            v_confirm = gateway_lifecycle.verify_file(
                goal_lean, write_olean=True,
                axioms_for=fq_name if mfst.axioms_whitelist else None,
                workspace=workspace,
            )
            ok_confirm = "error" not in v_confirm and v_confirm.get("ok")
            if ok_confirm:
                forbidden = _grep_forbidden(final_text, mfst.forbidden_lemmas)
                if forbidden:
                    goal_lean.write_text(backup_text, encoding="utf-8")
                    return PipelineResult(outcome="failed",
                                          failure_reason="forbidden_lemma",
                                          failure_detail=forbidden)
                if mfst.axioms_whitelist:
                    if v_confirm.get("axiom_error"):
                        goal_lean.write_text(backup_text, encoding="utf-8")
                        return PipelineResult(outcome="failed",
                                              failure_reason="axiom_violation",
                                              failure_detail=v_confirm["axiom_error"])
                    used = set(v_confirm.get("axioms") or [])
                    rogue = used - set(mfst.axioms_whitelist)
                    if rogue:
                        goal_lean.write_text(backup_text, encoding="utf-8")
                        return PipelineResult(outcome="failed",
                                              failure_reason="axiom_violation",
                                              failure_detail=f"rogue axioms: {sorted(rogue)}")
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

    # Spawn sandbox snapshot. Replaces the prior ad-hoc `.backup`
    # mechanism: SpawnWorkspace records goal_lean's pre-pipeline bytes
    # into `.attempts/<pid>/sandbox/`. Rollback (non-commit exit OR
    # daemon-startup sweep recovery) restores real goal_lean from
    # that snapshot. `restore_to_snapshot` is called between in-
    # pipeline retries so each retry sees pristine state.
    # See docs/archive/spawn_sandbox.md.
    from .. import spawn_sandbox as _sandbox_mod
    workspace_ctx = _sandbox_mod.SpawnWorkspace(
        workspace, pipeline_id, real_paths=[goal_lean])

    def _restore_backup() -> None:
        """Restore goal_lean from the spawn sandbox snapshot. Called
        between in-pipeline retries and on parse-fail paths."""
        workspace_ctx.restore_to_snapshot(goal_lean)

    def builder_spawn(ctx: SpawnCtx) -> int:
        # Always start from the pristine snapshot. Agent's --resume
        # session memory carries warm context; LSP slot state is in
        # the gateway worker. On-disk goal_lean is reset each entry
        # so prior-spawn apply_edits never leak into the next view.
        _restore_backup()

        # Cold start (and fresh-rescue, which is also cold-with-fresh-
        # sid): fresh Context.md compile (snapshot Manifest + goal
        # history at this exact attempt). For fresh-rescue, the helper
        # has already written `_prior_analysis.md` to attempts_dir;
        # the cold prompt's `is_fresh_rescue` flag injects a Read
        # directive so the agent consumes it before any other action.
        # Warm: skip — agent's session memory carries the Context from
        # the prior call; retry_context inlines the prior lake error.
        if ctx.cold:
            context.compile_context(conn, goal=goal, mfst=mfst,
                                  attempts_dir=ctx.attempts_dir,
                                  kind="builder")

        # Register a gateway session so claude's MCP tools operate on
        # goal_lean's content via the shared worker pool. Snapshot was
        # taken once before the retry loop; pristine restore happened
        # at the top of this function.
        mcp_config_path = _write_mcp_config(
            attempts_dir=ctx.attempts_dir,
            workspace=workspace,
            target=goal_lean,
            pipeline_id=pipeline_id,
            problem=goal["problem"],
        )

        return agent.spawn_llm(
            kind="builder",
            prompt_path=PROMPT_DIR / "builder.md",
            problem_dir=problem_dir,
            attempts_dir=ctx.attempts_dir,
            session_id=ctx.sid,
            is_retry=not ctx.cold,
            retry_context=ctx.retry_context,
            mcp_config_path=mcp_config_path,
            inline_prompt=ctx.inline_prompt,
            timeout_sec_override=ctx.budget_override,
        )

    def builder_parse() -> "PipelineResult":  # noqa: F821
        patches = _safe_glob(attempts_dir, "patch*.lean")
        if not patches:
            _restore_backup()
            return PipelineResult(
                outcome="failed", failure_reason="agent_no_output",
                failure_detail="no patch*.lean",
            )
        patch = patches[0]
        patch_text = patch.read_text(encoding="utf-8")

        # Phase 6 single-output: agent's metadata lives in patch.lean's
        # leading comment block. The `-- decline: <directive>` directive
        # (one of DECLINE_DIRECTIVES) maps to a structured failure_reason
        # via DECLINE_TO_FAILURE_REASON; cascade_one then routes by that
        # reason. Unknown directive strings (typos / partial migration
        # / future extensions) fall through to the generic `agent_declined`
        # branch — same destination as `needs_decomposition`, which is
        # the safe legacy default. The `## ...description...` block under
        # the directive is preserved verbatim in proposal_md and projected
        # to downstream context.md.
        leading = _extract_leading_comments(patch_text)
        decline = _extract_decline_reason(leading)
        if decline is not None:
            _restore_backup()
            reason = DECLINE_TO_FAILURE_REASON.get(decline, "agent_declined")
            return PipelineResult(
                outcome="failed", failure_reason=reason,
                failure_detail=f"builder declined: {decline}",
                proposal_md=leading,
            )

        forbidden = _grep_forbidden(patch_text, mfst.forbidden_lemmas)
        if forbidden:
            _restore_backup()
            return PipelineResult(
                outcome="failed", failure_reason="forbidden_lemma",
                failure_detail=forbidden, proposal_md=leading,
            )

        # Stage: copy patch over goal lean. Backup was already taken at
        # spawn entry — overwrite goal_lean with the agent's final
        # patch.lean (the output contract).
        shutil.copy2(patch, goal_lean)
        # Verify-unification (see docs/archive/verify_unification.md):
        # one /verify round trip elaborates the patch in a warm worker,
        # writes the .olean for downstream cascade consumers, and runs
        # `#print axioms` against the resulting environment. Replaces
        # the prior check_build + lake build + lake env lean chain.
        from .. import gateway_lifecycle
        fq_name = f"Problems.{goal['problem']}.{goal['slug']}"
        v = gateway_lifecycle.verify_file(
            goal_lean, write_olean=True,
            axioms_for=fq_name if mfst.axioms_whitelist else None,
            workspace=workspace,
        )
        if "error" in v:
            _restore_backup()
            return PipelineResult(
                outcome="failed", failure_reason="lake_build_error",
                failure_detail=f"verify infra error: {v['error']}",
                proposal_md=leading,
            )
        if not v.get("ok"):
            err_lines = "\n".join(
                f"line {d.get('line','?')}:{d.get('col','?')}  "
                f"{d.get('severity','?')}: {d.get('message','')}"
                for d in (v.get("diagnostics") or [])
                if d.get("severity") == "error"
            )
            _restore_backup()
            return PipelineResult(
                outcome="failed", failure_reason="lake_build_error",
                failure_detail=diagnostics.annotate_failure_detail(
                    err_lines or "(no error diagnostics returned)"),
                proposal_md=leading,
            )
        # Annotation is a hard success condition: an empty leading-
        # comment block means the agent skipped documentation. Roll
        # back to the sorry-stub backup and retry.
        if not leading.strip():
            _restore_backup()
            return PipelineResult(
                outcome="failed",
                failure_reason="agent_no_annotation",
                failure_detail="patch built but had no leading comment block",
            )
        # Axiom whitelist check on the just-collected axiom set.
        if mfst.axioms_whitelist:
            if v.get("axiom_error"):
                _restore_backup()
                return PipelineResult(
                    outcome="failed", failure_reason="axiom_violation",
                    failure_detail=f"axiom probe failed: {v['axiom_error']}",
                    proposal_md=leading,
                )
            used = set(v.get("axioms") or [])
            rogue = used - set(mfst.axioms_whitelist)
            if rogue:
                _restore_backup()
                return PipelineResult(
                    outcome="failed", failure_reason="axiom_violation",
                    failure_detail=f"rogue axioms: {sorted(rogue)}",
                    proposal_md=leading,
                )
        # Success: nothing to undo on goal_lean — promote_to_alias
        # via verify housekeeping will handle the alias rewrite
        # separately. Sandbox commit is marked at pipeline outer.
        return PipelineResult(outcome="proved", proposal_md=leading)

    def builder_postmortem(sid: str) -> None:
        _attempt_postmortem(
            kind="builder",
            prompt_path=PROMPT_DIR / "builder_postmortem.md",
            problem_dir=problem_dir,
            attempts_dir=attempts_dir,
            session_id=sid,
        )

    def builder_reflection(sid: str, result) -> None:
        from ._reflection import attempt_reflection, _reflection_enabled
        from .. import config
        if not _reflection_enabled(workspace):
            return
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

    # SpawnWorkspace: rolls back goal_lean from sandbox snapshot on
    # non-commit exit (exception or — recovered via sweep — daemon
    # crash). On a proved outcome, Builder's parse-success path has
    # written the agent's proof into goal_lean (this IS the commit);
    # we mark the sandbox committed so __exit__ skips the snapshot
    # rollback. Non-success outcomes leave goal_lean drifted; restore
    # from snapshot before __exit__ so cascade housekeeping sees
    # pristine state.
    result = None
    with workspace_ctx as ws:
        try:
            result = run_with_session_retries(
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
        finally:
            if result is None or result.outcome != "proved":
                # Helper crashed or returned non-success; restore
                # goal_lean to pre-spawn pristine so the next dispatch
                # / cascade sees the original stub.
                _restore_backup()
        if result.outcome == "proved":
            # Agent's proof is the commit; sandbox marked committed
            # so __exit__ doesn't roll it back.
            ws.commit(real_writes=())
    return result
