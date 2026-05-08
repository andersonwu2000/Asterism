"""Backward pipeline. OR-parallel-safe decomposition: reserves a fresh
strategy id, writes scratch + namespaced sub-goal files at strategy-
isolated paths, runs Lean kernel isDefEq dedupe to collapse equivalent
sub-goals to alias bodies, places everything atomically.

Phase 2 LSP swap: Backward spawns claude with an LSP MCP server
(`Tooling.lsp_mcp_server`) attached, target = `goal_lean`. The agent
uses `apply_edit` / `goal_at` / `errors_at` to validate that each
proposed sub-claim's statement type-checks before writing the final
`new_*.lean` + `patch.lean` outputs to attempts_dir. Backward's
output protocol is unchanged (multi-file `new_<slug>.lean` +
`patch.lean`); LSP is just an in-session validation sandbox.

Because the agent may apply_edit `goal_lean` during exploration,
each spawn snapshots `goal_lean` to a `.backup` file before the
spawn and restores it on every exit path — Backward's contract is
"goal_lean unchanged; outputs are in attempts_dir + proofs/".

Public entry point: `run_backward`. Backward-specific helpers
(`_ensure_imports_subgoal`, `_try_promote_sorry_free`,
`_parse_entry_kind`, `_resolve_slug_collisions`) live here. Shared
helpers (`_grep_forbidden`, `_attempt_postmortem`, `_spawn_failure`,
`_safe_glob`, `_signature_prefix`, `_normalize_signature`,
`_build_strategy_skeleton`, `_inject_imports_for_subs`,
`_lean_path_to_module`, `_lake_build_batch`, `_write_mcp_config`,
`PipelineResult`, `PROMPT_DIR`, `DECLINE_*`, `_extract_decline_reason`,
`_extract_leading_comments`, `_drafts`, `_extract_statement_from_lean`,
`_slug_from_filename`) are imported from the package root.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

from .. import agent, db, dedupe, diagnostics, manifest
from . import _axiom


# Sub-goal slug pattern: lowercase letter start, then lowercase letters,
# digits, underscore. Length is bounded separately (≤ 60) so the regex
# stays simple. Picked at agent time per `prompts/backward.md` "Write".
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _resolve_slug_collisions(
    sub_meta: list[tuple[str, Path]],
    existing_slugs: set[str],
) -> tuple[list[tuple[str, str, Path]], dict[str, str]]:
    """Pure helper: assign a final slug for each agent-picked (orig_slug,
    src_path), suffixing `_<n>` (n ≥ 2) when the original collides with
    `existing_slugs` or with another sub-goal already resolved in this
    batch.

    Returns `(resolved, rename_map)` where:
      * `resolved` is `[(orig_slug, final_slug, path), ...]` in input
        order. `final_slug == orig_slug` for non-colliding entries.
      * `rename_map: {orig_slug: final_slug}` only contains entries that
        were renamed; empty if the agent's choices were already unique.

    No filesystem side effects — the caller does file rename + content
    rewrite based on `rename_map`.
    """
    used = set(existing_slugs)
    resolved: list[tuple[str, str, Path]] = []
    rename_map: dict[str, str] = {}
    for orig, path in sub_meta:
        final = orig
        if final in used:
            n = 2
            while f"{orig}_{n}" in used:
                n += 1
            final = f"{orig}_{n}"
            rename_map[orig] = final
        used.add(final)
        resolved.append((orig, final, path))
    return resolved, rename_map


# ---------------------------------------------------------------------
# Backward-specific helpers (no shared callers as of writing)
# ---------------------------------------------------------------------

def _ensure_imports_subgoal(
    content: str, *, problem: str, workspace: Path,
) -> str:
    """Prepend `import Mathlib` and `import Problems.<problem>.Defs`
    (when the problem ships a `Defs.lean`) if missing. Idempotent —
    skips any line already present.

    Without `Defs`, problem-level custom symbols (e.g. SG's `Collinear`)
    are unresolved; a strict agent following the prompt's "framework
    auto-injects imports" instruction writes none, and Lean falls back
    to whatever `import Mathlib` exposes (e.g. Mathlib's universe-poly
    `Collinear (k : Type*) ...`), breaking elaboration.
    """
    needed: list[str] = []
    if not re.search(r"(?m)^import\s+Mathlib\b", content):
        needed.append("import Mathlib")
    defs_path = workspace / "Problems" / problem / "Defs.lean"
    if defs_path.exists():
        defs_module = f"Problems.{problem}.Defs"
        if not re.search(rf"(?m)^import\s+{re.escape(defs_module)}\b",
                         content):
            needed.append(f"import {defs_module}")
    if not needed:
        return content
    return "\n".join(needed) + "\n\n" + content


# Backward-placement convention: each `new_<sub_slug>.lean` should land
# with body `:= by sorry`. Agents occasionally inline a full proof
# instead (observed on SG s75_sub_4 — agent collapsed the sub-goal with
# `by_contra + ring + nlinarith`). When that happens AND axioms are in
# whitelist, we skip the now-redundant Backward dispatch and mark the
# sub-goal proved upfront. The check is fast: `\bsorry\b` substring
# match first (microseconds; 99% of placements have sorry); only the
# rare sorry-free case pays the axiom-probe cost.
_SORRY_RE = re.compile(r"\b(?:sorry|sorryAx)\b")


def _try_promote_sorry_free(
    *, dest: Path, problem: str, slug: str, workspace: Path,
    axioms_whitelist: list[str],
) -> tuple[bool, str]:
    """If `dest` is sorry-free AND its `#print axioms` set ⊆ whitelist,
    return (True, msg). Otherwise (False, reason).

    The strategy's batch lake build at the caller's site already
    confirmed the file compiles, so the literal `\\bsorry\\b` substring
    check is the cheap pre-filter; the real authority is `axiom_probe`.
    """
    try:
        content = dest.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"
    if _SORRY_RE.search(content):
        return False, "body contains sorry"
    return _axiom.axiom_probe_file(
        workspace, dest, problem=problem, slug=slug,
        whitelist=axioms_whitelist,
    )


# `entry_kind: Builder` or `entry_kind: Backward` directive — the
# Backward agent annotates each `new_<slug>.lean` with this comment so
# the framework knows whether to dispatch this sub-goal to Builder
# (one-shot tactic + LLM patch) or skip straight to Backward
# decomposition. Comment-form (not YAML frontmatter) so it sits next to
# the theorem definition the agent is reasoning about.
_ENTRY_KIND_RE = re.compile(
    r"(?m)^\s*--\s*entry_kind\s*:\s*(Builder|Backward)\b"
)


def _parse_entry_kind(lean_text: str) -> str:
    """Extract the `-- entry_kind: ...` directive from a sub-goal lean
    file. Returns 'Builder' or 'Backward' (capitalized as in the DB
    enum); defaults to 'Builder' if the directive is absent or
    unrecognized. The default mirrors the legacy attempts-only routing
    so a missing directive doesn't change behavior."""
    m = _ENTRY_KIND_RE.search(lean_text)
    return m.group(1) if m else "Builder"


# ---------------------------------------------------------------------
# Pipeline entry
# ---------------------------------------------------------------------

def run_backward(conn: sqlite3.Connection, *, goal_id: int,
                 workspace: Path, mfst: manifest.Manifest,
                 pipeline_id: str) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner Backward then persists or clears
    the partial-output draft (F55) so a future spawn on this same goal
    sees the in-flight PROPOSAL.md from the prior failed/timed-out
    attempt instead of starting from scratch.

    Outcomes:
      - `success`: strategy committed → clear any prior draft.
      - `moot`: goal terminated by parallel cascade → no useful draft.
      - `failed` with `failure_reason == "goal_no_longer_open"`: the
        race-guard fired because a sibling (re)decomposed or shelved
        this goal mid-spawn. The persisted PROPOSAL.md is moot for any
        future Backward — clear instead of persisting a stale draft
        that would mislead a re-decomposition if the goal later reopens.
      - anything else (failed / exhausted with retryable reasons):
        persist what the spawn wrote.
    """
    from . import PipelineResult, _drafts
    goal_row = db.get_goal(conn, goal_id)
    if goal_row is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")
    problem_dir = workspace / "Problems" / goal_row["problem"]
    result = _run_backward_inner(conn, goal_id=goal_id, workspace=workspace,
                                 mfst=mfst, pipeline_id=pipeline_id)
    if (result.outcome in ("success", "moot")
            or result.failure_reason == "goal_no_longer_open"):
        _drafts.clear_partial(problem_dir=problem_dir, kind="backward",
                              goal_id=goal_id)
    else:
        attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
        _drafts.persist_partials(attempts_dir=attempts_dir,
                                 problem_dir=problem_dir,
                                 kind="backward", goal_id=goal_id)
    return result


def _run_backward_inner(conn: sqlite3.Connection, *, goal_id: int,
                        workspace: Path, mfst: manifest.Manifest,
                        pipeline_id: str) -> "PipelineResult":  # noqa: F821
    """OR-parallel-safe Backward — Phase 7 in-pipeline retry.

    Each invocation reserves a fresh strategy id and writes its scratch +
    namespaced sub-goal files at strategy-isolated paths. Multiple
    concurrent Backwards on the same parent therefore never collide on
    the filesystem, the goals table (slug uniqueness), or the parent's
    own lean_path (which is left untouched until Verify wins).

    Phase 7 — strategy_id is reserved once before the retry helper loop
    and stays stable across all in-pipeline retries (so the agent's
    session memory anchored on `theorem s<sid_token>` remains valid
    after `--resume`). The former F53/A cross-pipeline strategy reuse
    is retired because each pipeline now mints fresh sid + strategy_id
    (no cross-pipeline session continuity to misalign).
    """
    from . import (
        PipelineResult, PROMPT_DIR,
        _attempt_postmortem, _build_strategy_skeleton,
        _extract_decline_reason, _extract_leading_comments,
        _extract_statement_from_lean, _grep_forbidden,
        _inject_imports_for_subs, _is_sorry_stub, _lake_build_batch,
        _lean_path_to_module, _normalize_signature,
        _safe_glob, _signature_prefix, _slug_from_filename,
        _write_mcp_config,
        DECLINE_PARENT_TYPE_INFEASIBLE,
    )
    from ._retry import SpawnCtx, run_with_session_retries
    from .. import dispatcher  # late: SHELVE_THRESHOLD live value

    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = workspace / "Problems" / goal["problem"]
    namespace = f"Problems.{goal['problem']}"

    # Build the F52 skeleton text once. Used by spawn_fn (cold) to
    # pre-populate attempts_dir/patch.lean and by parse_fn for the
    # signature lock check.
    parent_abs_for_skeleton = workspace / goal["lean_path"]
    try:
        parent_text = parent_abs_for_skeleton.read_text(encoding="utf-8")
    except OSError as exc:
        return PipelineResult(outcome="failed",
                              failure_reason="missing_parent_stub",
                              failure_detail=str(exc))

    # Reserve strategy_id once for the entire pipeline. Cleaned up on
    # any non-success outcome at the bottom of this function.
    strategy_id = db.insert_strategy(
        conn, goal_id=goal_id, lean_path=goal["lean_path"],
        created_by=pipeline_id, proposal_md="", scratch_path="",
    )
    sid_token = f"s{strategy_id}"

    skeleton = _build_strategy_skeleton(
        parent_text,
        parent_slug=goal["slug"],
        sid_token=sid_token,
        namespace=namespace,
    )
    if skeleton is None:
        db.update_strategy_status(conn, strategy_id, "dead")
        return PipelineResult(
            outcome="failed",
            failure_reason="parent_stub_not_decomposable",
            failure_detail=(
                f"theorem {goal['slug']} not found in {goal['lean_path']} "
                f"(may have been promoted by a sibling already)"
            ),
        )
    skeleton_signature = _normalize_signature(
        _signature_prefix(skeleton, sid_token))

    # In-loop _abort: returns failure WITHOUT marking strategy dead.
    # The outer cleanup at the bottom of this function marks it dead
    # if the helper's final outcome isn't 'success'.
    def _abort(reason: str, detail: str = "",
               proposal_md: str = "") -> "PipelineResult":  # noqa: F821
        return PipelineResult(
            outcome="failed", failure_reason=reason,
            failure_detail=detail, proposal_md=proposal_md,
        )

    # LSP swap (Phase 2): agent edits goal_lean in-session via
    # apply_edit to validate sub-claim statements. Backward's contract
    # is "goal_lean unchanged on exit" (decomposition outputs go to
    # attempts_dir → proofs/, NOT to goal_lean), so we snapshot before
    # each spawn and restore on every parse exit path.
    goal_lean = parent_abs_for_skeleton
    backup_path = goal_lean.with_suffix(goal_lean.suffix + ".backup")

    def _restore_backup() -> None:
        if backup_path.exists():
            shutil.copy2(backup_path, goal_lean)
            backup_path.unlink()

    def backward_spawn(ctx: SpawnCtx) -> int:
        # Rescue path — prior spawn watchdog-killed mid-thinking.
        # Resume the same session, send inline force-ship prompt
        # (180s cap). patch.lean still has whatever skeleton/edits
        # the killed turn produced (or the original cold-start
        # skeleton if it never wrote); the rescue agent has session
        # memory of its prior thinking and is asked to ship the
        # decomposition as-is.
        if ctx.rescue_prompt:
            from ..llm.base import RESCUE_BUDGET_SEC
            shutil.copy2(goal_lean, backup_path)
            mcp_config_path = _write_mcp_config(
                attempts_dir=ctx.attempts_dir,
                workspace=workspace, target=goal_lean,
            )
            return agent.spawn_llm(
                kind="backward",
                prompt_path=PROMPT_DIR / "backward.md",
                problem_dir=problem_dir,
                attempts_dir=ctx.attempts_dir,
                session_id=ctx.sid, is_retry=True,
                retry_context=None,
                mcp_config_path=mcp_config_path,
                is_rescue=True, rescue_prompt=ctx.rescue_prompt,
                timeout_sec_override=RESCUE_BUDGET_SEC,
            )

        # Cold start: agent has no session memory to resume. Compile
        # Context.md fresh and write the F52 skeleton so the agent's
        # first Read of patch.lean shows a clean `theorem s<sid_token>
        # ... := by sorry` template.
        # Warm: skip both — agent's --resume picks up Context from
        # prior turn, and patch.lean keeps whatever the agent wrote
        # last iteration so retry_context-driven fixes can be
        # incremental.
        if ctx.cold:
            agent.compile_context(conn, goal=goal, mfst=mfst,
                                  attempts_dir=ctx.attempts_dir,
                                  strategy_id=strategy_id,
                                  kind="backward")
            (ctx.attempts_dir / "patch.lean").write_text(
                skeleton, encoding="utf-8")

        # Snapshot goal_lean (the parent theorem's source file) and
        # write the MCP config so claude spawns lsp_mcp_server as a
        # stdio child. Agent uses LSP for in-session validation, but
        # goal_lean is restored to this snapshot on parse exit.
        shutil.copy2(goal_lean, backup_path)
        mcp_config_path = _write_mcp_config(
            attempts_dir=ctx.attempts_dir,
            workspace=workspace,
            target=goal_lean,
        )

        return agent.spawn_llm(
            kind="backward",
            prompt_path=PROMPT_DIR / "backward.md",
            problem_dir=problem_dir,
            attempts_dir=ctx.attempts_dir,
            session_id=ctx.sid,
            is_retry=not ctx.cold,
            retry_context=ctx.retry_context,
            mcp_config_path=mcp_config_path,
        )

    def backward_parse() -> "PipelineResult":  # noqa: F821
        # LSP swap: restore goal_lean from the pre-spawn backup on
        # every exit path. Backward's contract is "goal_lean
        # unchanged"; the agent may have used apply_edit to test the
        # decomposition, but the actual outputs (new_*.lean +
        # patch.lean → proofs/_strategy_*.lean) live elsewhere.
        try:
            return _backward_parse_and_commit(
                conn=conn, goal=goal, goal_id=goal_id, mfst=mfst,
                workspace=workspace, attempts_dir=attempts_dir,
                strategy_id=strategy_id, sid_token=sid_token,
                skeleton_signature=skeleton_signature,
                _abort=_abort,
                _safe_glob=_safe_glob,
                _extract_leading_comments=_extract_leading_comments,
                _extract_decline_reason=_extract_decline_reason,
                DECLINE_PARENT_TYPE_INFEASIBLE=DECLINE_PARENT_TYPE_INFEASIBLE,
                _normalize_signature=_normalize_signature,
                _signature_prefix=_signature_prefix,
                _is_sorry_stub=_is_sorry_stub,
                _grep_forbidden=_grep_forbidden,
                _slug_from_filename=_slug_from_filename,
                _lake_build_batch=_lake_build_batch,
                _inject_imports_for_subs=_inject_imports_for_subs,
                _lean_path_to_module=_lean_path_to_module,
                _extract_statement_from_lean=_extract_statement_from_lean,
            )
        finally:
            _restore_backup()

    def backward_postmortem(sid: str) -> None:
        _attempt_postmortem(
            kind="backward",
            prompt_path=PROMPT_DIR / "backward_postmortem.md",
            problem_dir=problem_dir,
            attempts_dir=attempts_dir,
            session_id=sid,
        )

    def backward_reflection(sid: str, result) -> None:
        from ._reflection import attempt_reflection
        from .. import config
        from ._reflection import _reflection_enabled
        if not _reflection_enabled(workspace):
            return
        cap = config.get(
            "lessons.cap", default=10, cast=int, workspace=workspace,
        )
        attempt_reflection(
            kind="backward",
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

    try:
        result = run_with_session_retries(
            conn=conn,
            goal_id=goal_id,
            pipeline_id=pipeline_id,
            budget_threshold=dispatcher.SHELVE_THRESHOLD,
            shelve_threshold=dispatcher.SHELVE_THRESHOLD,
            attempts_dir=attempts_dir,
            spawn_fn=backward_spawn,
            parse_fn=backward_parse,
            postmortem_fn=backward_postmortem,
            rescue_prompt=(
                "Killed mid-think. Ship now: patch.lean + new_<slug>.lean "
                "stubs (`:= by sorry` ok). No analysis."
            ),
            workspace=workspace,
            reflection_fn=backward_reflection,
        )
    finally:
        # LSP swap final guard: spawn rc != 0 paths (timeout, quota,
        # agent crash) skip parse_fn entirely, so the parse-side
        # `_restore_backup` doesn't fire. Belt-and-suspenders here:
        # whatever the helper's exit, ensure goal_lean is back to its
        # pre-spawn state. Idempotent — `.backup` may already be gone.
        _restore_backup()

    # Cleanup: any non-success outcome leaves the strategy at 'proposed'
    # with no scratch_path / no sub-goal links. Mark it dead so
    # `strategies_ready_for_verify` doesn't hang on it.
    if result.outcome != "success":
        db.update_strategy_status(conn, strategy_id, "dead")

    return result


def _backward_parse_and_commit(
    *, conn, goal, goal_id, mfst, workspace, attempts_dir,
    strategy_id, sid_token, skeleton_signature, _abort,
    _safe_glob, _extract_leading_comments, _extract_decline_reason,
    DECLINE_PARENT_TYPE_INFEASIBLE,
    _normalize_signature, _signature_prefix, _is_sorry_stub,
    _grep_forbidden, _slug_from_filename, _lake_build_batch,
    _inject_imports_for_subs, _lean_path_to_module,
    _extract_statement_from_lean,
) -> "PipelineResult":  # noqa: F821
    """Parse + dedupe + place + build + commit pass for one Backward
    spawn. Called by the in-pipeline retry helper after a successful
    spawn (rc=0). Returns 'success' on commit, 'failed' on any
    structural / build problem; the caller decides whether to retry
    (helper) or escalate (cascade).

    Strategy mark-dead cleanup is the OUTER caller's responsibility —
    this function leaves the strategy at 'proposed' even on failure
    so warm retries can run against the same row.
    """
    from . import PipelineResult
    patches = _safe_glob(attempts_dir, "patch*.lean")
    if not patches:
        return _abort("parse_proposal_fail", "no patch.lean")
    main_patch_text = patches[0].read_text(encoding="utf-8")

    # Phase 6 single-output: leading comment block on patch.lean is the
    # strategy's annotation source (later propagates to the parent goal
    # when this strategy wins Verify). `-- decline: <reason>` on the
    # leading block routes through the decline channel.
    leading = _extract_leading_comments(main_patch_text)
    decline = _extract_decline_reason(leading)
    if decline == DECLINE_PARENT_TYPE_INFEASIBLE:
        return _abort(
            "agent_infeasible",
            ("backward reports parent type infeasible; "
             "leading comments must include counterexample"),
            leading,
        )

    if not leading.strip():
        return _abort(
            "agent_no_annotation",
            "patch.lean present but had no leading comment block; "
            "strategy rationale is required for goal annotation propagation.",
            leading,
        )

    # F52 signature check applies to both decomp + leaf-bypass paths.
    agent_signature = _normalize_signature(
        _signature_prefix(main_patch_text, sid_token))
    if agent_signature != skeleton_signature:
        return _abort(
            "patch_signature_mismatch",
            f"agent edited the locked signature\n"
            f"expected: {skeleton_signature[:300]}\n"
            f"got:      {agent_signature[:300]}",
            leading,
        )

    new_subs = _safe_glob(attempts_dir, "new_*.lean")
    if not new_subs:
        # Phase 6.5 — Backward leaf-bypass salvage. Mirrors
        # `_try_promote_sorry_free` at the sub-goal level: when the
        # agent over-delivers (writes patch.lean with a complete proof
        # body and no decomposition), the framework registers a
        # 0-subgoal strategy rather than thrashing with parse_proposal_
        # fail. Verify housekeeping picks it up next tick (lake build
        # the patch + promote_to_alias parent → goal proved). If patch
        # body is `:= by sorry` and there are no subs and no decline
        # directive, it's truly empty output → real parse_proposal_fail.
        if _is_sorry_stub(main_patch_text):
            return _abort(
                "parse_proposal_fail",
                "patch=1 new=0 with sorry body and no decline directive; "
                "need decomposition (new_*.lean), a leaf-style proof, or "
                "a `-- decline:` directive.",
                leading,
            )
        forbidden = _grep_forbidden(main_patch_text, mfst.forbidden_lemmas)
        if forbidden:
            return _abort("forbidden_lemma", forbidden, leading)
        proofs_dir = workspace / "Problems" / goal["problem"] / "proofs"
        proofs_dir.mkdir(parents=True, exist_ok=True)
        scratch_dest = proofs_dir / f"_strategy_{sid_token}.lean"
        shutil.copy2(patches[0], scratch_dest)
        try:
            ok, err = _lake_build_batch(workspace, [scratch_dest])
        except Exception as exc:  # noqa: BLE001
            scratch_dest.unlink(missing_ok=True)
            return _abort(
                "lake_build_error",
                diagnostics.annotate_failure_detail(str(exc)),
                leading,
            )
        if not ok:
            scratch_dest.unlink(missing_ok=True)
            return _abort(
                "lake_build_error",
                diagnostics.annotate_failure_detail(err),
                leading,
            )
        # Race guard mirrors the decomp path's check at line ~666.
        fresh = db.get_goal(conn, goal_id)
        if fresh is None or fresh["status"] not in ("open", "attempting"):
            scratch_dest.unlink(missing_ok=True)
            current = fresh["status"] if fresh else "missing"
            return _abort(
                "goal_no_longer_open",
                f"goal {goal_id} transitioned to {current!r} during this "
                f"Backward's leaf-bypass run; aborting to avoid orphan strategy.",
                leading,
            )
        scratch_rel = scratch_dest.relative_to(workspace).as_posix()
        db.update_strategy_scratch_path(conn, strategy_id, scratch_rel)
        conn.execute("UPDATE strategies SET proposal_md = ? WHERE id = ?",
                     (leading, strategy_id))
        conn.commit()
        print(f"[backward leaf-bypass] strategy={sid_token} → ready_for_verify",
              flush=True)
        return PipelineResult(outcome="success", proposal_md=leading)

    # Forbidden-lemma grep covers patch + every sub-goal stub.
    all_text = "\n".join([main_patch_text] +
                          [p.read_text(encoding="utf-8") for p in new_subs])
    forbidden = _grep_forbidden(all_text, mfst.forbidden_lemmas)
    if forbidden:
        return _abort("forbidden_lemma", forbidden, leading)

    # Validate slug naming: agent-picked descriptive identifier.
    # Charset `[a-z][a-z0-9_]*`, length ≤ 60. Cross-problem collision is
    # auto-suffixed (`_2`, `_3`, ...) by the framework — agent doesn't
    # do its own uniqueness check. The strategy's own theorem (`s<sid>`)
    # and patch file (`_strategy_s<sid>.lean`) are framework-locked.
    # Only sub-goal filenames `new_<slug>.lean` carry agent-picked slugs.
    # Same-slug-twice within a batch is impossible at filesystem level
    # (second write of the same `new_<slug>.lean` overwrites the first
    # in attempts_dir, so only one file reaches the parse stage).
    sub_meta: list[tuple[str, Path]] = []  # (slug, source_in_attempts)
    for ns in new_subs:
        slug = _slug_from_filename(ns.name)
        if not slug:
            return _abort(
                "naming_violation",
                f"sub-goal filename {ns.name!r} yields empty slug",
                leading,
            )
        if len(slug) > 60:
            return _abort(
                "naming_violation",
                f"sub-goal slug {slug!r} exceeds max length 60",
                leading,
            )
        if not _SLUG_RE.match(slug):
            return _abort(
                "naming_violation",
                f"sub-goal slug {slug!r} must match [a-z][a-z0-9_]* "
                f"(lowercase ascii start, then ascii/digits/underscore)",
                leading,
            )
        sub_meta.append((slug, ns))

    # Auto-suffix cross-batch collisions. Helper is pure; we apply the
    # filesystem side effects here based on the returned rename_map.
    existing_slugs = {
        row["slug"] for row in conn.execute(
            "SELECT slug FROM goals WHERE problem = ?",
            (goal["problem"],),
        ).fetchall()
    }
    resolved, rename_map = _resolve_slug_collisions(
        sub_meta, existing_slugs)
    if rename_map:
        # Rewrite theorem-declaration name + rename file in attempts_dir
        # for each renamed sub-goal. `count=1` + `\btheorem\s+SLUG\b`
        # only touches the declaration; comments / other identifiers
        # that happen to share substrings stay intact.
        for orig, final, path in resolved:
            if orig == final:
                continue
            new_path = path.parent / f"new_{final}.lean"
            content = path.read_text(encoding="utf-8")
            content = re.sub(
                rf"\btheorem\s+{re.escape(orig)}\b",
                f"theorem {final}",
                content,
                count=1,
            )
            new_path.write_text(content, encoding="utf-8")
            path.unlink()
        # Update patch.lean to point at the renamed sub-goals. Word-
        # boundary regex prevents corrupting unrelated identifiers that
        # share a substring prefix. main_patch_text (the in-memory copy
        # used for the signature check above) is not used after this
        # point, so leaving it stale is fine; the on-disk file is what
        # mv'es to scratch_dest later.
        patch_text = patches[0].read_text(encoding="utf-8")
        for orig, new in rename_map.items():
            patch_text = re.sub(
                rf"\b{re.escape(orig)}\b", new, patch_text)
        patches[0].write_text(patch_text, encoding="utf-8")
    sub_meta = [
        (final, (path.parent / f"new_{final}.lean") if orig != final else path)
        for orig, final, path in resolved
    ]

    # Dedupe scan: batch-call Lean kernel isDefEq for all candidate
    # sub-goals × eligible ancestors in one subprocess. Hits → write an
    # alias lean file that delegates to canonical via `apply <;>
    # assumption`; insert the alias goal as 'proved' (its proof IS the
    # alias body).
    candidates_for_dedupe: list[tuple[str, str]] = []
    for slug, src in sub_meta:
        try:
            candidates_for_dedupe.append(
                (slug, src.read_text(encoding="utf-8")))
        except OSError:
            candidates_for_dedupe.append((slug, ""))
    canonical_for = dedupe.find_canonicals_batch(
        conn, workspace,
        problem=goal["problem"],
        parent_goal_id=goal_id,
        candidates=candidates_for_dedupe,
    )

    # Compute permanent paths under proofs/. Strategy patch path includes
    # sid_token (framework-locked, collision-free). Sub-goal `L_<slug>.lean`
    # paths use the agent-picked slug, whose problem-local uniqueness was
    # verified above; if the slug check passed, the path cannot collide.
    proofs_dir = workspace / "Problems" / goal["problem"] / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    scratch_filename = f"_strategy_{sid_token}.lean"
    scratch_dest = proofs_dir / scratch_filename
    sub_dests = [(slug, proofs_dir / f"L_{slug}.lean") for slug, _ in sub_meta]

    placed: list[Path] = []
    try:
        # Place sub-goal files: alias body for dedupe-hits, original
        # content for novel sub-goals.
        for (slug, src), (_, dest), canonical_id in zip(
            sub_meta, sub_dests, canonical_for,
        ):
            if canonical_id is not None:
                canonical = db.get_goal(conn, canonical_id)
                canonical_module = _lean_path_to_module(
                    workspace, workspace / canonical["lean_path"])
                original_content = src.read_text(encoding="utf-8")
                dest.write_text(
                    dedupe.build_alias_content(
                        original_content=original_content,
                        canonical_module=canonical_module,
                        canonical_slug=canonical["slug"],
                    ),
                    encoding="utf-8",
                )
                print(f"[dedupe] {slug} → goal {canonical_id} "
                      f"({canonical['slug']})", flush=True)
            else:
                content = _ensure_imports_subgoal(
                    src.read_text(encoding="utf-8"),
                    problem=goal["problem"], workspace=workspace,
                )
                dest.write_text(content, encoding="utf-8")
            placed.append(dest)
        shutil.copy2(patches[0], scratch_dest)
        placed.append(scratch_dest)

        # F52 — auto-inject `import` lines for sub-goal modules into
        # the strategy patch. Agents reliably forget at least one;
        # framework-managed imports avoid an entire class of
        # `unknown identifier` errors at lake build.
        sub_dest_paths = [dest for _, dest in sub_dests]
        _inject_imports_for_subs(workspace, scratch_dest, sub_dest_paths)

        # F23 — single multi-target lake invocation. Lake's internal
        # scheduler builds independent sub-goal files in parallel and
        # serializes the strategy assembly (which imports the subs)
        # after, replacing the prior serial per-file loop. On a 4-sub
        # strategy the wall-clock dropped from ~5×80s to ~max(80s)+80s.
        # Caller (annotate_failure_detail) smart-truncates stderr to
        # surface error / warning lines.
        ok, err = _lake_build_batch(workspace, placed)
        if not ok:
            raise RuntimeError(f"lake build failed: {err}")

        # F24-A — race guard: between this Backward's dispatch and now
        # (which is up to several minutes due to claude CLI + lake build),
        # an OR-parallel sibling may have shelved or proved this goal.
        # Either way our new strategy is moot. Abort cleanly so cascade
        # has nothing to mutate; clean up sub-goal files we placed.
        # cascade_one's no-op guard handles the same race on its side
        # (defense in depth) — this layer prevents the orphan strategy +
        # sub-goal rows from ever reaching the DB.
        fresh = db.get_goal(conn, goal_id)
        if fresh is None or fresh["status"] not in ("open", "attempting"):
            for p in placed:
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass
            current = fresh["status"] if fresh else "missing"
            return _abort(
                "goal_no_longer_open",
                f"goal {goal_id} transitioned to {current!r} during this "
                f"Backward's run; aborting to avoid orphan strategy.",
                leading,
            )

        # All passed — INSERT goals + link via strategy_subgoals.
        # Dedupe-hits are inserted as already-'proved' (alias body is
        # the proof); novel sub-goals start 'open'. Sorry-free
        # placements with whitelisted axioms also start 'proved' —
        # spares a redundant Backward/Builder spawn that would just
        # `promote_to_alias` over the same content.
        linked_ids: list[int] = []
        for (slug, dest), canonical_id in zip(sub_dests, canonical_for):
            stmt = _extract_statement_from_lean(dest)
            rel = dest.relative_to(workspace).as_posix()
            entry_kind = _parse_entry_kind(
                dest.read_text(encoding="utf-8"))
            new_gid = db.insert_goal(
                conn, problem=goal["problem"], slug=slug,
                lean_path=rel, statement=stmt, origin="backward",
                depth=goal["depth"] + 1,
                entry_kind=entry_kind,
            )
            if canonical_id is not None:
                db.update_goal_status(conn, new_gid, "proved")
                # F42 — record alias relationship so prune retains the
                # canonical (in case it's an orphan from a dead strategy)
                # for as long as this alias is alive.
                db.set_alias_target(conn, new_gid, canonical_id)
            else:
                ok, msg = _try_promote_sorry_free(
                    dest=dest, problem=goal["problem"], slug=slug,
                    workspace=workspace,
                    axioms_whitelist=mfst.axioms_whitelist,
                )
                if ok:
                    db.update_goal_status(conn, new_gid, "proved")
                    print(f"[skip-dispatch] {slug} → proved ({msg})",
                          flush=True)
            linked_ids.append(new_gid)
        for pos, gid in enumerate(linked_ids):
            db.link_subgoal(conn, strategy_id=strategy_id,
                            subgoal_id=gid, position=pos)

        scratch_rel = scratch_dest.relative_to(workspace).as_posix()
        db.update_strategy_scratch_path(conn, strategy_id, scratch_rel)
        conn.execute("UPDATE strategies SET proposal_md = ? WHERE id = ?",
                     (leading, strategy_id))
        conn.commit()

        return PipelineResult(outcome="success", proposal_md=leading)

    except Exception as exc:
        # Cleanup: remove only this strategy's files (other strategies
        # untouched). Mark this strategy dead.
        for p in placed:
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        return _abort(
            "lake_build_error",
            diagnostics.annotate_failure_detail(str(exc)),
            leading,
        )
