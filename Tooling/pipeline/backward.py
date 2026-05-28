"""Backward pipeline. OR-parallel-safe decomposition: reserves a fresh
strategy id, writes scratch + namespaced sub-goal files at strategy-
isolated paths, runs Lean kernel isDefEq dedupe to collapse equivalent
sub-goals to alias bodies, places everything atomically.

LSP-backed agent: Backward spawns claude with an `--mcp-config`
pointing at the long-living `Tooling.lsp_gateway` HTTP server,
target = `attempts_dir/patch.lean`. The agent uses `apply_edit` /
`goal_at` / `errors_at` directly on `patch.lean` (which is pre-
seeded with the strategy skeleton: imports + `theorem s<sid_token>
... := by sorry`). The agent's last `apply_edit` produces the final
patch.lean body — no transcription step. Sub-goal stubs are written
to `attempts_dir/new_<slug>.lean` via the Write tool, then
verified standalone via `validate_file`.

Single-writer invariant for `goal_lean` (parent's Root.lean):
the agent NEVER writes to it. Only the framework's `promote_to_alias`
rewrites it on verify success. This eliminates the worker/main race
where the worker's _restore_backup could stomp on a concurrently-
written promote_to_alias alias. Backward's contract remains
"goal_lean unchanged by this pipeline; outputs are in attempts_dir
+ proofs/".

Public entry point: `run_backward`. Backward-specific helpers
(`_ensure_imports_subgoal`, `_try_promote_sorry_free`,
`_parse_entry_kind`, `_resolve_slug_collisions`) live here. Shared
helpers (`_grep_forbidden`, `_attempt_postmortem`, `_spawn_failure`,
`_safe_glob`, `_signature_prefix`, `_normalize_signature`,
`_build_strategy_skeleton`, `_inject_imports_for_subs`,
`_lean_path_to_module`, `_write_mcp_config`,
`PipelineResult`, `PROMPT_DIR`, `DECLINE_*`, `_extract_decline_reason`,
`_extract_leading_comments`, `_drafts`, `_extract_statement_from_lean`,
`_slug_from_filename`) are imported from the package root.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

from .. import agent
from ..agent import context
from ..state import db, manifest
from ..quality import dedupe, diagnostics
from . import _axiom
from ._cite_gate import _PROBLEM_IMPORT_RE, _resolve_cite_dependencies


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
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
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
                 pipeline_id: str,
                 decision_id: int | None = None,
                 ) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner Backward then persists or clears
    the partial-output draft so a future spawn on this same goal sees
    the in-flight PROPOSAL.md from the prior failed/timed-out attempt
    instead of starting from scratch.

    Phase 2 — `decision_id` flows from the spawning queue row (non-NULL
    only when a Strategist Inject decision emitted this entry). Passed
    through to `compile_context` for the `## Strategist brief` section.

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
    problem_dir = db.problem_dir(workspace, goal_row["problem"])
    result = _run_backward_inner(conn, goal_id=goal_id, workspace=workspace,
                                 mfst=mfst, pipeline_id=pipeline_id,
                                 decision_id=decision_id)
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
                        pipeline_id: str,
                        decision_id: int | None = None,
                        ) -> "PipelineResult":  # noqa: F821
    """OR-parallel-safe Backward — Phase 7 in-pipeline retry.

    Each invocation reserves a fresh strategy id and writes its scratch +
    namespaced sub-goal files at strategy-isolated paths. Multiple
    concurrent Backwards on the same parent therefore never collide on
    the filesystem, the goals table (slug uniqueness), or the parent's
    own lean_path (which is left untouched until Verify wins).

    Phase 7 — strategy_id is reserved once before the retry helper loop
    and stays stable across all in-pipeline retries (so the agent's
    session memory anchored on `theorem s<sid_token>` remains valid
    after `--resume`). The former cross-pipeline strategy reuse is
    retired because each pipeline now mints fresh sid + strategy_id
    (no cross-pipeline session continuity to misalign).
    """
    from . import (
        PipelineResult, PROMPT_DIR,
        _attempt_postmortem, _build_strategy_skeleton,
        _extract_decline_reason, _extract_leading_comments,
        _extract_statement_from_lean, _grep_forbidden,
        _inject_imports_for_subs, _is_sorry_stub,
        _lean_path_to_module, _normalize_signature,
        _safe_glob, _signature_prefix, _slug_from_filename,
        _write_mcp_config,
        DECLINE_TO_FAILURE_REASON,
    )
    from ._retry import SpawnCtx, run_with_session_retries
    from ..core import dispatcher  # late: SHELVE_THRESHOLD live value

    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, goal["problem"])
    namespace = f"Problems.{goal['problem']}"

    # Build the strategy skeleton text once. Used by spawn_fn (cold)
    # to pre-populate attempts_dir/patch.lean and by parse_fn for the
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
    # If this Backward was spawned by an Inject(Backward) decision,
    # link the just-reserved strategy back to the decision row so
    # propagate_inject_outcome_from_strategy can fill the decision's
    # outcome when the strategy reaches terminal — and through it
    # fire `inject_batch_done` for the originating batch.
    if decision_id is not None:
        db.set_inject_decision_produced_strategy(
            conn, decision_id, strategy_id)
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

    # MCP target = attempts_dir/patch.lean. Agent's apply_edit writes
    # to this sandbox file, never touches goal_lean (Root.lean).
    # promote_to_alias (run by verify_housekeeping in main thread) is
    # the single writer of goal_lean — no race possible with worker.
    # Previously this code path snapshotted goal_lean via
    # SpawnWorkspace and _restore_backup'd between retries / on exit;
    # with apply_edit no longer targeting goal_lean, neither snapshot
    # nor restore is needed.

    def backward_spawn(ctx: SpawnCtx) -> int:
        # Cold start (and fresh-rescue, which is also cold-with-fresh-
        # sid): agent has no session memory to resume. Compile
        # Context.md fresh and write the strategy skeleton so the agent's
        # first Read of patch.lean shows a clean `theorem s<sid_token>
        # ... := by sorry` template. For fresh-rescue, the helper has
        # already written `_prior_analysis.md` to attempts_dir; the
        # cold prompt's `is_fresh_rescue` flag injects a Read directive
        # so the agent consumes it before any other action.
        # Warm: skip both — agent's --resume picks up Context from
        # prior turn, and patch.lean keeps whatever the agent wrote
        # last iteration so retry_context-driven fixes can be
        # incremental.
        patch_lean = ctx.attempts_dir / "patch.lean"
        if ctx.cold:
            context.compile_context(conn, goal=goal, mfst=mfst,
                                  attempts_dir=ctx.attempts_dir,
                                  strategy_id=strategy_id,
                                  kind="backward",
                                  decision_id=decision_id)
            patch_lean.write_text(skeleton, encoding="utf-8")

        # Register a gateway session so claude's MCP tools operate on
        # patch.lean (in attempts_dir/) via the shared worker pool.
        # The skeleton already includes `import Mathlib` etc., so LSP
        # elaborates it standalone in the worker slot.
        mcp_config_path = _write_mcp_config(
            attempts_dir=ctx.attempts_dir,
            workspace=workspace,
            target=patch_lean,
            pipeline_id=pipeline_id,
            problem=goal["problem"],
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
            inline_prompt=ctx.inline_prompt,
            timeout_sec_override=ctx.budget_override,
        )

    def backward_parse() -> "PipelineResult":  # noqa: F821
        # No goal_lean restore needed — agent's apply_edit targets
        # patch.lean (sandboxed in attempts_dir), so goal_lean is
        # never mutated during the spawn. Parse reads patch.lean +
        # new_*.lean from attempts_dir; the only writer of goal_lean
        # is verify_housekeeping's promote_to_alias (main thread).
        return _backward_parse_and_commit(
            conn=conn, goal=goal, goal_id=goal_id, mfst=mfst,
            workspace=workspace, attempts_dir=attempts_dir,
            strategy_id=strategy_id, sid_token=sid_token,
            skeleton_signature=skeleton_signature,
            _abort=_abort,
            _safe_glob=_safe_glob,
            _extract_leading_comments=_extract_leading_comments,
            _extract_decline_reason=_extract_decline_reason,
            DECLINE_TO_FAILURE_REASON=DECLINE_TO_FAILURE_REASON,
            _normalize_signature=_normalize_signature,
            _signature_prefix=_signature_prefix,
            _is_sorry_stub=_is_sorry_stub,
            _grep_forbidden=_grep_forbidden,
            _slug_from_filename=_slug_from_filename,
            _inject_imports_for_subs=_inject_imports_for_subs,
            _lean_path_to_module=_lean_path_to_module,
            _extract_statement_from_lean=_extract_statement_from_lean,
        )

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
        from ..core import config
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

    # No SpawnWorkspace — agent writes are confined to attempts_dir
    # (patch.lean, new_*.lean), which WorkArea manages via the
    # .attempts/<pid>/ rmtree on exit. goal_lean has a single writer
    # (verify_housekeeping → promote_to_alias) and needs no per-spawn
    # snapshot.
    #
    # try/finally guards the reserved strategy row (inserted at line
    # 380 above) against escaping exceptions — gateway crash, subprocess
    # SIGKILL, internal pipeline bug. Without it, the row sits forever
    # at status='proposed' with empty proposal_md/scratch_path/no
    # sub-goals; recovery's startup sweep eventually cleans it but
    # mid-lifecycle accumulation goes unbounded.
    _INFRA_REASONS = {
        "quota_exhausted", "spawn_fast_fail", "missing_dep",
        "gateway_unreachable", "transient_timeout",
    }
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
            workspace=workspace,
            reflection_fn=backward_reflection,
            decision_id=decision_id,
        )
    except BaseException:
        # Escaped exception — strategy row is still in placeholder state
        # if no commit ever happened. Delete to match _INFRA_REASONS
        # semantics (agent never produced anything → no forensic value).
        # Re-raise so dispatcher's worker-exception handler can synthesize
        # the cascade as usual.
        row = conn.execute(
            "SELECT proposal_md, scratch_path FROM strategies WHERE id=?",
            (strategy_id,),
        ).fetchone()
        if row and not (row["proposal_md"] or row["scratch_path"]):
            db.delete_strategy(conn, strategy_id)
            conn.commit()
        raise

    # Cleanup: non-success outcomes split by whether the agent ran.
    #
    # #101 — Infra failures (quota / spawn / network / slot timeout) mean
    # the agent never produced anything: no proposal_md, no scratch_path,
    # no strategy_subgoals link. Marking these rows `dead` leaves forensic
    # noise that misleads observation (SG run accumulated 8587 such empty
    # shells). DELETE them — the row never reflected real agent output.
    #
    # Agent-side failures (parse / decline / verify / sorry / signature
    # mismatch / etc.) are real attempts: the agent did work and we want
    # the row to survive so TREE.md / `_strategy_dead_cause` can explain
    # why it died, even though the strategy itself didn't succeed.
    if result.outcome != "success":
        if result.failure_reason in _INFRA_REASONS:
            db.delete_strategy(conn, strategy_id)
        else:
            db.update_strategy_status(conn, strategy_id, "dead")

    return result


def _backward_parse_and_commit(
    *, conn, goal, goal_id, mfst, workspace, attempts_dir,
    strategy_id, sid_token, skeleton_signature, _abort,
    _safe_glob, _extract_leading_comments, _extract_decline_reason,
    DECLINE_TO_FAILURE_REASON,
    _normalize_signature, _signature_prefix, _is_sorry_stub,
    _grep_forbidden, _slug_from_filename,
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

    # Bail-for-postmortem detection (Backward rescue option d): the
    # rescue prompt offers the agent a "write _progress.md and exit"
    # path when not confident in any split. Discriminator must be
    # strict — false-positive bail loses real strategy commits. Bail
    # only when the agent's *only* meaningful output is _progress.md:
    # patch.lean is unchanged from the cold-start skeleton (no leading
    # comment, sorry body) AND no new_<slug>.lean files. Observed in
    # SG run #6 (g266 sid=d4230668): a productive cold-spawn agent
    # cargo-culted the postmortem format and wrote _progress.md after
    # finishing a valid split — without this discriminator, that win
    # would be discarded as bail. failure_reason `agent_bailed` is in
    # `_TERMINAL_DECLINE_REASONS`, so the helper exits the retry loop;
    # the outer `run_backward` wrapper then persists `_progress.md` to
    # .drafts/ for the next cold dispatch.
    progress = attempts_dir / "_progress.md"
    if progress.exists():
        try:
            note = progress.read_text(encoding="utf-8").strip()
        except OSError:
            note = ""
        if note:
            bail_leading = _extract_leading_comments(main_patch_text)
            bail_new_subs = _safe_glob(attempts_dir, "new_*.lean")
            if (not bail_leading.strip()
                    and not bail_new_subs
                    and _is_sorry_stub(main_patch_text)):
                return _abort(
                    "agent_bailed",
                    "agent wrote _progress.md and left patch.lean as "
                    "skeleton with no sub-goals (Backward rescue "
                    "option d).",
                )

    # Phase 6 single-output: leading comment block on patch.lean is the
    # strategy's annotation source (later propagates to the parent goal
    # when this strategy wins Verify). `-- decline: <reason>` on the
    # leading block routes through the decline channel.
    leading = _extract_leading_comments(main_patch_text)
    decline = _extract_decline_reason(leading)
    if decline is not None:
        # Map directive to DB failure_reason. Unknown directive strings
        # (typos / partial migration) fall through to agent_declined —
        # cascade_one's generic-failure branch catches them. Backward
        # cannot send `needs_decomposition` (Builder-only); if seen here
        # the prompt failed to constrain the agent — log + treat as
        # declined.
        reason = DECLINE_TO_FAILURE_REASON.get(decline, "agent_declined")
        return _abort(
            reason,
            f"backward declined: {decline}",
            leading,
        )

    if not leading.strip():
        return _abort(
            "agent_no_annotation",
            "patch.lean present but had no leading comment block; "
            "strategy rationale is required for goal annotation propagation.",
            leading,
        )

    # Signature check applies to both decomp + leaf-bypass paths.
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
        # Citation gate (leaf-bypass: no decomposition, axiom probe
        # runs at submit). `allow_auto_link=False` — leaf-bypass cannot
        # tolerate cited unproved siblings because the immediate axiom
        # probe sees their `:= by sorry` body through the import chain.
        # Cited open siblings must be handled via the decomp path's
        # auto-link mechanism (which defers verification until cited
        # goal proves).
        _, cite_err = _resolve_cite_dependencies(
            conn, problem=goal["problem"], patch_text=main_patch_text,
            declared_slugs=set(), allow_auto_link=False,
        )
        if cite_err:
            return _abort("cite_unproved_sibling", cite_err, leading)
        proofs_dir = db.problem_dir(workspace, goal["problem"]) / "proofs"
        proofs_dir.mkdir(parents=True, exist_ok=True)
        scratch_dest = proofs_dir / f"_strategy_{sid_token}.lean"
        shutil.copy2(patches[0], scratch_dest)
        # Verify-unification: gateway worker pool elaborates the
        # strategy file AND writes its olean to disk in one round trip.
        # The olean is needed downstream by `verify_strategy`, which
        # later builds the parent alias against this strategy module.
        # Single-file verify (no cross-module deps within the strategy
        # itself; it imports Mathlib + Defs, both already warm in every
        # slot).
        from ..lsp import lifecycle as gateway_lifecycle
        # Run axiom probe at acceptance gate (single round trip — gateway
        # already computes axiom info during elaboration; passing
        # axioms_for just asks for it back). Catches the common Sonnet
        # leaf-bypass failure mode where the agent ships a patch whose
        # body looks complete + LSP reports "0 errors / no goals" but
        # Lean's elaborator silently filled in `sorryAx` synthetic
        # placeholders for unification failures it treated as warnings.
        # Pre-(a): such a patch passed acceptance, entered ready_for_
        # verify, then verify_strategy detected sorryAx + killed the
        # strategy + reopened the goal — wasting one promote_to_alias +
        # parent build (~5-10s) and triggering the cascade-vs-verify
        # race window. Post-(a): caught here with no scratch promotion,
        # no race surface.
        fq_name = (
            f"Problems.{goal['problem']}.{sid_token}"
            if mfst.axioms_whitelist else None
        )
        v = gateway_lifecycle.verify_file(
            scratch_dest, write_olean=True,
            axioms_for=fq_name, workspace=workspace,
        )
        if "error" in v:
            scratch_dest.unlink(missing_ok=True)
            return _abort(
                "lake_build_error",
                diagnostics.annotate_failure_detail(
                    f"verify infra error: {v['error']}"),
                leading,
            )
        if not v.get("ok"):
            err_lines = "\n".join(
                f"line {d.get('line','?')}:{d.get('col','?')}  "
                f"{d.get('severity','?')}: {d.get('message','')}"
                for d in (v.get("diagnostics") or [])
                if d.get("severity") == "error"
            )
            scratch_dest.unlink(missing_ok=True)
            return _abort(
                "lake_build_error",
                diagnostics.annotate_failure_detail(
                    err_lines or "(no error diagnostics returned)"),
                leading,
            )
        if mfst.axioms_whitelist:
            if v.get("axiom_error"):
                scratch_dest.unlink(missing_ok=True)
                return _abort(
                    "axiom_violation",
                    f"leaf-bypass axiom probe error: {v['axiom_error']}",
                    leading,
                )
            used = set(v.get("axioms") or [])
            rogue = used - set(mfst.axioms_whitelist)
            if rogue:
                scratch_dest.unlink(missing_ok=True)
                return _abort(
                    "axiom_violation",
                    f"leaf-bypass rogue axioms: {sorted(rogue)}",
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

    # Bug B (polar 2026-05-23): each `new_<slug>.lean` must contain a
    # real `(theorem|def|structure|class) <slug>` declaration. A
    # comment-only or placeholder file passes slug-filename + lake-
    # build checks silently (lake elaborates an empty namespace fine),
    # then later Backward attempts to decompose this stub-less goal
    # hit `parent_stub_not_decomposable` repeatedly until the goal
    # exhausts attempts. Validate at commit time using the same
    # `signature_prefix` regex that `_build_strategy_skeleton` runs at
    # decomp time — if the regex can't find the declaration later,
    # reject now instead of persisting the garbage.
    for slug, src in sub_meta:
        try:
            text = src.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if not _signature_prefix(text, slug):
            return _abort(
                "parse_proposal_fail",
                f"new_{slug}.lean has no `(theorem|def|structure|class) "
                f"{slug} ...` declaration. If this sub-goal turned out "
                f"redundant during your decomposition, delete the file "
                f"before submitting (don't leave a placeholder comment).",
                leading,
            )

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

    # #112(a) — if any candidate matches a previously-disproved goal in
    # this problem (agent gave a counterexample, status='disproved'),
    # abort the whole strategy: the proposed approach recapitulates a
    # statement known false. Decline-style abort surfaces the offending
    # slug pairs so the next Backward (or the agent's retry context)
    # can see what was already disproved.
    #
    # Phase 2 — Tier 4 dedupe semantic shifted from 'shelved' (any
    # terminal) to 'disproved' (counterexample only). Soft-terminal
    # 'shelved' goals no longer trigger this abort.
    disproved_hits = [
        (slug, m.goal_id)
        for (slug, _), m in zip(sub_meta, canonical_for)
        if m is not None and m.kind == "disproved"
    ]
    if disproved_hits:
        detail = "; ".join(
            f"{slug} ≡ disproved goal {gid} "
            f"({db.get_goal(conn, gid)['slug']})"
            for slug, gid in disproved_hits
        )
        return _abort(
            "same_as_disproved",
            f"sub-goal(s) recapitulate a previously-disproved statement "
            f"in this problem: {detail}. Pick a different decomposition.",
            leading,
        )

    # Compute permanent paths under proofs/. Strategy patch path includes
    # sid_token (framework-locked, collision-free). Sub-goal `L_<slug>.lean`
    # paths use the agent-picked slug, whose problem-local uniqueness was
    # verified above; if the slug check passed, the path cannot collide.
    proofs_dir = db.problem_dir(workspace, goal["problem"]) / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    scratch_filename = f"_strategy_{sid_token}.lean"
    scratch_dest = proofs_dir / scratch_filename
    sub_dests = [(slug, proofs_dir / f"L_{slug}.lean") for slug, _ in sub_meta]

    placed: list[Path] = []
    try:
        # Place sub-goal files: alias body for dedupe-hits, original
        # content for novel sub-goals. By this point any disproved-kind
        # match has aborted via the same_as_disproved early-return above,
        # so a non-None `match` is guaranteed kind="alias".
        for (slug, src), (_, dest), match in zip(
            sub_meta, sub_dests, canonical_for,
        ):
            if match is not None:
                canonical_id = match.goal_id
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
                content = manifest.inject_defs_opens(
                    content, problem=goal["problem"], workspace=workspace,
                )
                dest.write_text(content, encoding="utf-8")
            placed.append(dest)
        shutil.copy2(patches[0], scratch_dest)
        # Inject Defs.lean opens into the strategy patch as well — the
        # patch carries the strategy body (which may reference `π` /
        # `Real.sin` etc. via Defs's shared notation) and must replay
        # opens for the same reason every other agent-authored file
        # does. See state/manifest.py:inject_defs_opens docstring.
        scratch_dest.write_text(
            manifest.inject_defs_opens(
                scratch_dest.read_text(encoding="utf-8"),
                problem=goal["problem"], workspace=workspace,
            ),
            encoding="utf-8",
        )
        placed.append(scratch_dest)

        # Auto-inject `import` lines for sub-goal modules into the
        # strategy patch. Agents reliably forget at least one;
        # framework-managed imports avoid an entire class of
        # `unknown identifier` errors at lake build.
        sub_dest_paths = [dest for _, dest in sub_dests]
        _inject_imports_for_subs(workspace, scratch_dest, sub_dest_paths)

        # Citation gate — classify cited siblings:
        #  - 'proved' siblings: pass through (legitimate citation)
        #  - 'open'/'attempting'/'pending_strategist_review' siblings:
        #    auto-linked as `strategy_subgoals` (the safe parallel
        #    pattern — strategy waits in 'proposed' until cited goal
        #    proves via `strategies_ready_for_verify`'s all-subgoals-
        #    proved check, then alias-rewrites up).
        #  - terminal-failed siblings (shelved/disproved/dead): reject
        #    (can't recover in this strategy).
        # Run after `_inject_imports_for_subs` so framework-injected
        # imports for declared sub-goals don't false-trigger.
        declared_slugs = {slug for slug, _ in sub_meta}
        auto_link_ids, cite_err = _resolve_cite_dependencies(
            conn, problem=goal["problem"],
            patch_text=scratch_dest.read_text(encoding="utf-8"),
            declared_slugs=declared_slugs, allow_auto_link=True,
        )
        if cite_err:
            for p in placed:
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass
            return _abort("cite_unproved_sibling", cite_err, leading)

        # Assembly gate — strategy body must contain no `sorry` placeholder.
        # `verify_strategy` is mechanical (promote_to_alias only); without
        # this scan, an agent that forgets to transcribe
        # `have h_<slug> := by sorry` → `have h_<slug> := <slug> <args>`
        # ships a sorry-bearing proof that elaborates fine (sorry is a
        # warning, not an error) but propagates sorryAx to `main`. In a
        # multi-problem workspace, `library.maybe_promote`'s root axiom
        # probe gates on ALL roots proved, so the failure can survive
        # indefinitely. See `_assembly.py` for design.
        from ._assembly import assembly_gate_check_sorry
        ok, msg = assembly_gate_check_sorry(scratch_dest)
        if not ok:
            for p in placed:
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass
            return _abort("patch_body_contains_sorry", msg, leading)

        # Verify-unification: sequential per-file verify through the
        # gateway worker pool (see docs/archive/verify_unification.md §3).
        # `placed` is in dependency order — sub-goal stubs first (each
        # independent, importing only Mathlib + Defs), strategy file
        # last (imports the sub-goal modules by name, resolves through
        # the .olean files we wrote in earlier iterations).
        from ..lsp import lifecycle as gateway_lifecycle
        for path in placed:
            v = gateway_lifecycle.verify_file(
                path, write_olean=True, workspace=workspace,
            )
            if "error" in v:
                raise RuntimeError(
                    f"verify infra error on {path.name}: {v['error']}"
                )
            if not v.get("ok"):
                err_lines = "\n".join(
                    f"{path.name}:{d.get('line','?')}:{d.get('col','?')}  "
                    f"{d.get('severity','?')}: {d.get('message','')}"
                    for d in (v.get("diagnostics") or [])
                    if d.get("severity") == "error"
                )
                raise RuntimeError(
                    f"lake build failed: "
                    f"{err_lines or 'no error diagnostics'}"
                )

        # Race guard: between this Backward's dispatch and now (which
        # is up to several minutes due to claude CLI + lake build), an
        # OR-parallel sibling may have shelved or proved this goal.
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
        for (slug, dest), match in zip(sub_dests, canonical_for):
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
            if match is not None:
                # Past the same_as_disproved early-return → kind="alias".
                db.update_goal_status(conn, new_gid, "proved")
                # Record alias relationship so prune retains the
                # canonical (in case it's an orphan from a dead strategy)
                # for as long as this alias is alive.
                db.set_alias_target(conn, new_gid, match.goal_id)
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
        # Auto-linked dependencies — cited siblings the citation gate
        # classified as parallel-buildable (open/attempting/pending_
        # strategist_review). Sorted for deterministic position
        # assignment. These extend `strategy_subgoals` past the
        # declared sub-goals so `strategies_ready_for_verify` blocks
        # until they prove — the strategy waits naturally for the
        # parallel-built lemma to land before alias-rewrite proceeds.
        next_pos = len(linked_ids)
        for offset, auto_gid in enumerate(sorted(auto_link_ids)):
            db.link_subgoal(conn, strategy_id=strategy_id,
                            subgoal_id=auto_gid, position=next_pos + offset)

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
