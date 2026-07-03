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

import sqlite3
from pathlib import Path

from .. import agent
from ..agent import context
from . import _presearch
from ..state import assemble, db, manifest, proof_store
from ..quality import diagnostics
from ._cite_gate import _resolve_cite_dependencies


def run_builder(conn: sqlite3.Connection, *, goal_id: int,
                workspace: Path, mfst: manifest.Manifest,
                pipeline_id: str,
                decision_id: int | None = None,
                ) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner pipeline then persists or clears
    the partial-output draft so a future spawn on this same goal
    sees the in-flight patch from the prior failed attempt instead of
    starting from scratch.

    Phase 2 — `decision_id` flows from the spawning queue row (non-NULL
    only when a Strategist Inject decision emitted this entry). Passed
    through to `compile_context` for the `## Strategist brief` section.

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
                                mfst=mfst, pipeline_id=pipeline_id,
                                decision_id=decision_id)
    if result.outcome in ("proved", "moot"):
        _drafts.clear_partial(problem_dir=problem_dir, kind="builder",
                              goal_id=goal_id)
        # Also drop any salvaged patch.lean from a prior orphan spawn
        # — once this one succeeded, the prior attempt is moot.
        _drafts.clear_partial_patch(problem_dir=problem_dir,
                                    kind="builder", goal_id=goal_id)
    else:
        attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
        _drafts.persist_partials(attempts_dir=attempts_dir,
                                 problem_dir=problem_dir,
                                 kind="builder", goal_id=goal_id, conn=conn)
    return result


def _run_builder_inner(conn: sqlite3.Connection, *, goal_id: int,
                       workspace: Path, mfst: manifest.Manifest,
                       pipeline_id: str,
                       decision_id: int | None = None,
                       ) -> "PipelineResult":  # noqa: F821
    from . import (
        PipelineResult, PROMPT_DIR,
        _attempt_postmortem, _extract_decline_reason,
        _extract_leading_comments, _grep_forbidden, _is_sorry_stub,
        _parse_hint_winner, _replace_proof_body,
        _safe_glob,
        DECLINE_TO_FAILURE_REASON,
    )
    from ._retry import SpawnCtx, run_lsp_edit_loop
    from ..core import dispatcher  # late: BUILDER_THRESHOLD live value

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

    def _commit_goal_lean(content: str) -> None:
        """Guarded write of this goal's OWN proof file. Routes through the
        ownership chokepoint (`place_proof`) so a mis-computed `goal_lean`
        pointing at a DIFFERENT goal's committed file raises ClobberError
        before touching disk, instead of silently clobbering it (the DB↔file
        drift class). For this goal's own path the guard always passes — it is
        defence against a future bug that hands Builder the wrong path."""
        proof_store.place_proof(
            conn, workspace, goal_id=goal_id,
            rel_path=goal["lean_path"], content=content)

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
        from ..lsp import lifecycle as gateway_lifecycle

        # Probe: `:= by hint` elaborates all `register_hint` tactics;
        # the `hint` tactic emits info diagnostics with a "Try these:
        # [apply] 🎉️ <tac>" block when it found a closer. We scan all
        # info diagnostics' message text for the marker. write_olean
        # is skipped (probe is throwaway).
        probe_text = _replace_proof_body(source, "hint")
        _commit_goal_lean(probe_text)
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
            _commit_goal_lean(final_text)
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
                    _commit_goal_lean(backup_text)
                    return PipelineResult(outcome="failed",
                                          failure_reason="forbidden_lemma",
                                          failure_detail=forbidden)
                if mfst.axioms_whitelist:
                    if v_confirm.get("axiom_error"):
                        _commit_goal_lean(backup_text)
                        return PipelineResult(outcome="failed",
                                              failure_reason="axiom_violation",
                                              failure_detail=v_confirm["axiom_error"])
                    used = set(v_confirm.get("axioms") or [])
                    rogue = used - set(mfst.axioms_whitelist)
                    if rogue:
                        _commit_goal_lean(backup_text)
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
        _commit_goal_lean(backup_text)

    # Phase 2: tactic_llm via in-pipeline retry helper.
    # Helper owns budget = BUILDER_THRESHOLD - goal.attempts (decision 1),
    # sid lifecycle (cold first, --resume thereafter), per-retry
    # forensic. Builder-specific spawn / parse / postmortem are closures
    # over the pipeline scope below.
    #
    # Sandbox model (parity with Backward, see backward.py:316-321):
    # `.attempts/<pid>/patch.lean` is the agent's scratch — apply_edit's
    # write-through goes there, and the agent's final `patch.lean`
    # output is parsed from the same file. goal_lean (the workspace
    # `proofs/L_<slug>.lean`) is untouched during the spawn and is
    # written exactly once, atomically, at commit time in
    # `builder_parse` after all checks pass. This removes the prior
    # SpawnWorkspace snapshot/restore machinery: there's no "dirty
    # workspace mid-spawn" window for crash recovery to repair.
    patch_lean = attempts_dir / "patch.lean"
    goal_lean_original = source   # already read above
    promote_done = False

    def _seed_patch_from_goal() -> None:
        """Initialize patch.lean to goal_lean's current content so the
        agent's first apply_edit / Read sees the original stub (or any
        partial draft persisted by `_drafts.persist_partials` is
        overwritten by the agent's own re-write — handled by spawn)."""
        patch_lean.write_text(goal_lean_original, encoding="utf-8")

    def _restore_goal_lean() -> None:
        """Undo a commit attempt on goal_lean. Only called after the
        final post-verify failure paths in `builder_parse` — i.e. once the
        `_commit_goal_lean` write has already mutated workspace and the
        subsequent verify/axiom check rejected the patch."""
        _commit_goal_lean(goal_lean_original)

    def builder_cold_prep(ctx: SpawnCtx) -> None:
        # Cold start: re-seed sandbox patch.lean from goal_lean's pristine
        # content + compile Context.md. Warm retries skip this — patch.lean
        # keeps whatever the agent wrote last iteration (the agent's --resume
        # session memory carries the context) so retry_context-driven fixes
        # stay incremental. The gateway-session registration + spawn itself
        # are owned by `run_lsp_edit_loop` (target=patch_lean): apply_edit's
        # write-through stays inside the sandbox; only builder_parse commits
        # to goal_lean.
        _seed_patch_from_goal()
        # target-1: per-node pre-search (once per node, cached). Writes the
        # candidate-lemma cache that compile_context's section then reads.
        _presearch.ensure_presearch(
            goal=goal, workspace=workspace, problem_dir=problem_dir,
            attempts_dir=ctx.attempts_dir, prompt_dir=PROMPT_DIR)
        context.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=ctx.attempts_dir,
                              kind="builder",
                              decision_id=decision_id)

    def builder_parse() -> "PipelineResult":  # noqa: F821
        nonlocal promote_done
        patches = _safe_glob(attempts_dir, "patch*.lean")
        if not patches:
            # Sandbox model: goal_lean was never touched — no restore.
            return PipelineResult(
                outcome="failed", failure_reason="agent_no_output",
                failure_detail="no patch*.lean",
            )
        patch = patches[0]
        patch_text = patch.read_text(encoding="utf-8")
        # Unified commit normalization (task #5 Step B): framework imports
        # (no-op on the seeded skeleton) + Defs opens + proved-sibling
        # imports, in ONE place — the same `assemble_for_commit` every
        # commit path runs, so validate and commit can't disagree on the
        # transforms. Write the patch back so the cite-gate + the commit
        # copy (which re-reads the file) both see it.
        _asm = assemble.assemble_for_commit(
            patch_text, problem=goal["problem"], workspace=workspace,
            conn=conn)
        if _asm.text != patch_text:
            patch_text = _asm.text
            patch.write_text(patch_text, encoding="utf-8")
        if _asm.injected_sibling_imports:
            print(f"[cite] auto-imported "
                  f"{len(_asm.injected_sibling_imports)} proved sibling(s): "
                  f"{', '.join(_asm.injected_sibling_imports)}", flush=True)

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
            reason = DECLINE_TO_FAILURE_REASON.get(decline, "agent_declined")
            return PipelineResult(
                outcome="failed", failure_reason=reason,
                failure_detail=f"builder declined: {decline}",
                proposal_md=leading,
            )

        forbidden = _grep_forbidden(patch_text, mfst.forbidden_lemmas)
        if forbidden:
            return PipelineResult(
                outcome="failed", failure_reason="forbidden_lemma",
                failure_detail=forbidden, proposal_md=leading,
            )

        # Citation gate — Builder is leaf-bypass (no decomposition);
        # reject any cited sibling not status='proved'. Without this,
        # Builder could import a shelved sibling's L_<slug>.lean
        # wrapper (whose underlying strategy is sorry-bearing), have
        # the lake verify succeed (sorry is a warning not an error),
        # and propagate sorryAx silently until root_integrity_gate
        # catches it many cycles later. Mirror of the leaf-bypass call
        # in backward.py around the leaf-bypass commit window.
        _, _, cite_err = _resolve_cite_dependencies(
            conn, problem=goal["problem"], patch_text=patch_text,
            declared_slugs=set(), allow_auto_link=False,
            workspace=workspace,
        )
        if cite_err:
            return PipelineResult(
                outcome="failed", failure_reason="cite_unproved_sibling",
                failure_detail=cite_err, proposal_md=leading,
            )

        # Annotation is a hard success condition: an empty leading-
        # comment block means the agent skipped documentation. Reject
        # before touching goal_lean.
        if not leading.strip():
            return PipelineResult(
                outcome="failed",
                failure_reason="agent_no_annotation",
                failure_detail="patch built but had no leading comment block",
            )

        # ---- Commit window opens here ----
        # Up to this point goal_lean is untouched. Now copy patch over
        # goal_lean and verify; on any failure below, restore goal_lean
        # from `goal_lean_original`. The commit window is the few
        # hundred ms between this copy and the post-verify decision.
        # Defs opens were already injected by the assemble_for_commit
        # normalization above (written back into the patch), so the commit
        # copy is byte-identical to what the gates saw.
        _commit_goal_lean(patch.read_text(encoding="utf-8"))
        promote_done = True
        # Verify-unification (see docs/archive/verify_unification.md):
        # one /verify round trip elaborates the patch in a warm worker,
        # writes the .olean for downstream cascade consumers, and runs
        # `#print axioms` against the resulting environment. Replaces
        # the prior check_build + lake build + lake env lean chain.
        # The single soundness gate: elaborate on the pipeline's OWN warm
        # slot (verify_in_session via the session token — Builder holds its
        # slot through this promote, released at WorkArea teardown), request
        # the axiom set, apply the unconditional sorryAx tripwire + whitelist
        # check. Shared with Forward + Backward (`_axiom.axiom_gate`);
        # upgraded from the prior borrow (verify_file) to own-slot to avoid
        # evicting a random tenant (the 2026-06-29 slot-thrash bug).
        from ._axiom import axiom_gate
        fq_name = f"Problems.{goal['problem']}.{goal['slug']}"
        gate = axiom_gate(
            goal_lean, fq_name=fq_name,
            whitelist=list(mfst.axioms_whitelist or []),
            workspace=workspace, attempts_dir=attempts_dir, write_olean=True)
        if not gate.ok:
            _restore_goal_lean()
            promote_done = False
            detail = gate.detail or ""
            if gate.failure_reason == "lake_build_error":
                detail = diagnostics.annotate_failure_detail(detail)
            return PipelineResult(
                outcome="failed", failure_reason=gate.failure_reason,
                failure_detail=detail, proposal_md=leading,
            )
        # Success: goal_lean has the agent's proof + verified olean.
        # promote_to_alias via verify housekeeping handles alias rewrite
        # separately.
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
        if not _reflection_enabled(workspace):
            return
        attempt_reflection(
            kind="builder",
            sid=sid,
            slug=goal["slug"],
            outcome=(result.failure_reason
                     if result.failure_reason
                     else result.outcome),
            goal_id=int(goal["id"]),
            problem=str(goal["problem"]),
            problem_dir=problem_dir,
            attempts_dir=attempts_dir,
            prompt_dir=PROMPT_DIR,
            workspace=workspace,
        )

    def builder_feedback(sid: str, result) -> None:
        from . import _feedback
        _feedback.attempt_feedback(
            kind="builder", sid=sid, slug=goal["slug"],
            outcome=(result.failure_reason or result.outcome),
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            workspace=workspace)

    def builder_death(result) -> None:
        from . import _feedback
        _feedback.record_death(
            workspace, kind="builder", slug=goal["slug"],
            problem=problem_dir.name,
            reason=result.failure_reason or result.outcome)

    # No SpawnWorkspace — agent writes are confined to attempts_dir
    # (patch.lean is the MCP apply_edit target), and goal_lean is
    # written exactly once inside builder_parse's commit window.
    # If the helper crashes between commit and verify (the only window
    # where goal_lean is dirty), `promote_done=True` flags it: the
    # outer finally restores goal_lean from snapshot.
    result = None
    try:
        result = run_lsp_edit_loop(
            conn=conn,
            goal_id=goal_id,
            pipeline_id=pipeline_id,
            budget_threshold=dispatcher.BUILDER_THRESHOLD,
            shelve_threshold=dispatcher.SHELVE_THRESHOLD,
            attempts_dir=attempts_dir,
            workspace=workspace,
            problem=goal["problem"],
            problem_dir=problem_dir,
            kind="builder",
            prompt_path=PROMPT_DIR / "builder.md",
            target=patch_lean,
            cold_prep_fn=builder_cold_prep,
            parse_fn=builder_parse,
            postmortem_fn=builder_postmortem,
            reflection_fn=builder_reflection,
            feedback_fn=builder_feedback,
            death_fn=builder_death,
            decision_id=decision_id,
        )
    finally:
        # Crash mid-commit (or any path where promote_done was set but
        # the final PipelineResult isn't 'proved') leaves goal_lean
        # drifted. Restore so cascade housekeeping sees pristine state.
        if promote_done and (result is None or result.outcome != "proved"):
            _restore_goal_lean()
    return result
