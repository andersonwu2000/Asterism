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
from ..state import db, manifest, proof_store, transitions
from ..quality import dedupe, diagnostics
from . import _axiom
from ._cite_gate import _PROBLEM_IMPORT_RE, _resolve_cite_dependencies


# Sub-goal slug pattern: lowercase letter start, then lowercase letters,
# digits, underscore. Length is bounded separately (≤ 60) so the regex
# stays simple. Picked at agent time per `prompts/backward.md` "Write".
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _normalize_slug(raw: str) -> "str | None":
    """Mechanically rewrite a slug that fails `_SLUG_RE` *only* because of
    uppercase letters (camelCase / PascalCase) into snake_case lowercase.

    `termIntegrableOn` → `term_integrable_on`, `HalfSpaceFTC` →
    `half_space_ftc`. Returns the normalized slug if it then matches
    `_SLUG_RE`, else None — a leading digit, punctuation, or unicode is not
    mechanically fixable, so the caller still rejects those as
    `naming_violation`.

    Why normalize instead of reject (backlog #3, 2026-06-13): the charset
    gate's hard-reject was a v1 stub (`cab25cc`) whose sibling — slug
    *collision* — already got the reject→auto-fix treatment (`948f557`).
    camelCase is just as mechanical; the case constraint (case-insensitive
    filesystem safety) is *preserved* by normalizing, and the agent
    demonstrably can't self-correct reliably (the failure message points at
    'slug' while the fix is a filename rename — P13 stokes burned a full
    Backward batch on `term_integrableOn`)."""
    # Insert `_` at lower/digit→upper and acronym→word boundaries.
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", raw)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    s = re.sub(r"_+", "_", s.lower()).strip("_")
    return s if _SLUG_RE.match(s) else None


def _strict_ancestor_slugs(conn, goal_id: int) -> "dict[str, str]":
    """`{slug: lean_path}` for every STRICT ancestor of `goal_id` on its
    live chain (walks up via `strategy_subgoals`; excludes `goal_id`
    itself). Used to detect a circular decomposition — a sub-goal that
    restates one of its own ancestors (backlog #4)."""
    rows = conn.execute(
        "WITH RECURSIVE ancestors(id) AS ("
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    WHERE ss.subgoal_id = ?"
        "  UNION"
        "  SELECT s.goal_id FROM strategies s"
        "    JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        "    JOIN ancestors a ON a.id = ss.subgoal_id"
        ") "
        "SELECT g.slug, g.lean_path FROM goals g WHERE g.id IN ancestors",
        (goal_id,),
    ).fetchall()
    return {r["slug"]: r["lean_path"] for r in rows}


def _theorem_head(text: str, slug: str) -> "str | None":
    """The whitespace-normalized `<binders> : <conclusion>` of
    `theorem <slug> ... :=` in `text`, for cheap structural comparison
    between a candidate sub-goal and an ancestor it may be restating."""
    m = re.search(
        r"\btheorem\s+" + re.escape(slug) + r"\b(.*?):=",
        text, re.DOTALL,
    )
    return " ".join(m.group(1).split()) if m else None


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


def _partition_sibling_reuse(
    conn, *, problem: str, goal_id: int, workspace: Path,
    sub_meta: list[tuple[str, Path]], existing_slugs: set[str],
    ancestor_slugs: "dict[str, str]",
) -> tuple[list[tuple[str, Path]], list[str], list[Path]]:
    """Split declared sub-goals into (kept, reuse_imports, dropped).

    A declared `new_<slug>.lean` whose slug names an EXISTING non-ancestor
    sibling in this problem (excluding the parent `goal_id` itself) with a
    verbatim-equivalent theorem head is a REUSE, not a new lemma. It is
    dropped from `kept` and the sibling's
    `import Problems.<problem>.proofs.L_<slug>` line is returned in
    `reuse_imports`, so the caller can cite the sibling instead of
    forking a `_2` duplicate. The citation gate then links / revives the
    sibling by its status (open → link, shelved → revive). `dropped`
    lists the redundant attempts-dir files for the caller to unlink.

    Stays in `kept` (→ `_resolve_slug_collisions`'s `_2` resolver):
      * novel slugs (not in `existing_slugs`),
      * strict ancestors (citing one is an import cycle),
      * the parent goal's own slug (self-cycle; dedupe `no_progress`
        handles it),
      * same-slug-DIFFERENT-statement collisions (genuine name clash),
      * `dead` / `disproved` siblings — the cite-gate rejects these
        (dead = wrong-as-stated, disproved = false), so citing would
        abort the whole strategy; keep for the `_2` resolver instead so
        the re-declaration becomes a FRESH re-statement under this
        strategy. (Consistency with the cite-gate's dead-reject, 6fc6ff4.)

    Pure decision — no filesystem mutation, so the caller owns the
    unlink + import injection. agent_feedback T8 / 91-92,110."""
    kept: list[tuple[str, Path]] = []
    reuse_imports: list[str] = []
    dropped: list[Path] = []
    for slug, ns in sub_meta:
        if slug not in existing_slugs or slug in ancestor_slugs:
            kept.append((slug, ns))
            continue
        sib = conn.execute(
            "SELECT id, lean_path, status FROM goals WHERE problem = ? "
            "  AND slug = ? AND alias_target_id IS NULL AND id != ? LIMIT 1",
            (problem, slug, goal_id),
        ).fetchone()
        if sib is None:
            kept.append((slug, ns))
            continue
        if str(sib["status"]) in ("dead", "disproved"):
            # Cite-gate would reject these → keep for a fresh `_2` fork.
            kept.append((slug, ns))
            continue
        try:
            cand_head = _theorem_head(ns.read_text(encoding="utf-8"), slug)
            sib_head = _theorem_head(
                (workspace / sib["lean_path"]).read_text(encoding="utf-8"),
                slug)
        except OSError:
            kept.append((slug, ns))
            continue
        if cand_head is None or cand_head != sib_head:
            # Same name, different statement → genuine collision.
            kept.append((slug, ns))
            continue
        reuse_imports.append(f"import Problems.{problem}.proofs.L_{slug}")
        dropped.append(ns)
    return kept, reuse_imports, dropped


def _partition_dedupe_reuse(
    conn, *, problem: str, workspace: Path,
    sub_meta: list[tuple[str, Path]], canonical_for: list,
) -> tuple[list[tuple[str, Path]], list, list[tuple[str, str, str]]]:
    """Split declared sub-goals by their dedupe verdict, extracting the
    `reuse` matches (dedupe `kind="reuse"` — a NON-proved in-problem twin
    found by SIGNATURE: open / attempting / pending_review / shelved) into
    citations of the twin.

    Unlike `_partition_sibling_reuse` (same-SLUG re-declaration → drop +
    import, no rename), a reuse match is a DIFFERENT-named but type-
    equivalent twin, so the caller must also rewrite the patch's slug
    reference to the twin's on-disk theorem name. Returns
    (kept_meta, kept_canon, reuse_rewrites) where each reuse_rewrite is
    (slug, twin_thm, twin_module). Pure decision — the caller applies the
    patch rewrite (`_apply_reuse_rewrites`); the citation gate then links /
    revives the twin by status (open → link, shelved → revive + link)."""
    from ..quality import dedupe as _dedupe
    from ._lake import lean_path_to_module
    kept_meta: list[tuple[str, Path]] = []
    kept_canon: list = []
    reuse_rewrites: list[tuple[str, str, str]] = []
    for (slug, src), match in zip(sub_meta, canonical_for):
        if match is None or getattr(match, "kind", None) != "reuse":
            kept_meta.append((slug, src))
            kept_canon.append(match)
            continue
        x = db.get_goal(conn, match.goal_id)
        if x is None:
            kept_meta.append((slug, src))
            kept_canon.append(match)
            continue
        try:
            x_text = (workspace / x["lean_path"]).read_text(encoding="utf-8")
        except OSError:
            x_text = ""
        x_thm = _dedupe._extract_theorem_name(x_text) or x["slug"]
        x_module = lean_path_to_module(
            workspace, workspace / x["lean_path"])
        reuse_rewrites.append((slug, x_thm, x_module))
        print(f"[dedupe] {slug} → reuse goal {match.goal_id} "
              f"({x['slug']}, status={x['status']}) — citing, no new "
              f"sub-goal", flush=True)
    return kept_meta, kept_canon, reuse_rewrites


def _apply_reuse_rewrites(text: str,
                          reuse_rewrites: list[tuple[str, str, str]]) -> str:
    r"""Rewrite a strategy patch for dedupe-reuse: for each
    (slug, twin_thm, twin_module), replace the bare `slug` token — the
    sub-goal value reference; `\bslug\b` skips the `h_<slug>` hypothesis
    name (no word boundary inside `h_…`) — with the twin's theorem name,
    and inject `import twin_module` after the last import. The citation
    gate then sees the import and auto-links / revives the twin."""
    for y_slug, x_thm, x_module in reuse_rewrites:
        text = re.sub(rf"\b{re.escape(y_slug)}\b", x_thm, text)
        if f"import {x_module}" not in text:
            lines = text.split("\n")
            last_imp = max(
                (i for i, ln in enumerate(lines)
                 if ln.startswith("import ")), default=-1)
            lines.insert(last_imp + 1, f"import {x_module}")
            text = "\n".join(lines)
    return text


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

# Line-level variant for stripping: consumes the whole directive line
# (including any trailing text and the newline) so removal leaves no
# blank residue. Anchored the same way as _ENTRY_KIND_RE.
_ENTRY_KIND_LINE_RE = re.compile(
    r"(?m)^[ \t]*--[ \t]*entry_kind[ \t]*:[ \t]*(?:Builder|Backward)\b.*\r?\n?"
)


def _parse_entry_kind(lean_text: str) -> str:
    """Extract the `-- entry_kind: ...` directive from a sub-goal lean
    file. Returns 'Builder' or 'Backward' (capitalized as in the DB
    enum); defaults to 'Builder' if the directive is absent or
    unrecognized. The default mirrors the legacy attempts-only routing
    so a missing directive doesn't change behavior."""
    m = _ENTRY_KIND_RE.search(lean_text)
    return m.group(1) if m else "Builder"


def _strip_entry_kind(lean_text: str) -> str:
    """Remove the `-- entry_kind:` directive line(s) once the framework
    has consumed it into the DB `goals.entry_kind` column. That column is
    the routing SoT thereafter, so the comment left in the permanent
    `proofs/L_<slug>.lean` is dead residue — and it propagates into the
    curated Library on migrate. Stripping at consume-time keeps the parse
    channel (agent still writes it in `new_<slug>.lean`) intact while
    keeping downstream files clean. Rationale comments below the
    directive sit on their own `--` lines and are untouched."""
    return _ENTRY_KIND_LINE_RE.sub("", lean_text)


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
                                 kind="backward", goal_id=goal_id, conn=conn)
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
        transitions.apply_strategy_transition(
            conn, strategy_id, "dead", event="skeleton_failed")
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
            retry_reason=ctx.retry_reason,
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
            workspace=workspace,
        )

    def backward_feedback(sid: str, result) -> None:
        from . import _feedback
        _feedback.attempt_feedback(
            kind="backward", sid=sid, slug=goal["slug"],
            outcome=(result.failure_reason or result.outcome),
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            workspace=workspace)

    def backward_death(result) -> None:
        from . import _feedback
        _feedback.record_death(
            workspace, kind="backward", slug=goal["slug"],
            problem=problem_dir.name,
            reason=result.failure_reason or result.outcome)

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
            feedback_fn=backward_feedback,
            death_fn=backward_death,
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
        elif result.outcome == "moot":
            # `moot` = the agent NEVER ran (retry pre-loop budget<=0, or a
            # cascade re-check bailed before any spawn). The reserved row is
            # an empty shell with no forensic value, exactly like an infra
            # death — discard it, not mark it `dead`. Leaving moots as `dead`
            # is what let the P13 4284 wedge moot-spin pile up 5458 empty dead
            # strategies on ONE goal (2026-06-15): BFS re-dispatched Backward
            # on the over-budget goal ~thousands of times, each reserving a
            # row then retry-mooting. Guard emptiness (mirroring the escaped-
            # exception handler above) so a mid-loop moot that somehow follows
            # a partial commit keeps its content; an unrun shell is deleted.
            row = conn.execute(
                "SELECT proposal_md, scratch_path FROM strategies WHERE id=?",
                (strategy_id,),
            ).fetchone()
            if row and (row["proposal_md"] or row["scratch_path"]):
                transitions.apply_strategy_transition(
                    conn, strategy_id, "dead", event="moot_retain")
            else:
                db.delete_strategy(conn, strategy_id)
        else:
            transitions.apply_strategy_transition(
                conn, strategy_id, "dead", event="agent_failed")

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
        _, _, cite_err = _resolve_cite_dependencies(
            conn, problem=goal["problem"], patch_text=main_patch_text,
            declared_slugs=set(), allow_auto_link=False,
            workspace=workspace,
        )
        if cite_err:
            return _abort("cite_unproved_sibling", cite_err, leading)
        proofs_dir = db.problem_dir(workspace, goal["problem"]) / "proofs"
        proofs_dir.mkdir(parents=True, exist_ok=True)
        scratch_dest = proofs_dir / f"_strategy_{sid_token}.lean"

        def _rm_scratch() -> None:
            proof_store.remove_proof(
                conn, workspace,
                rel_path=scratch_dest.relative_to(workspace).as_posix(),
                owner_goal_id=None)

        proof_store.atomic_write(
            scratch_dest, patches[0].read_text(encoding="utf-8"))
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
        # Always request the axiom set (near-free — computed during
        # elaboration) for the UNCONDITIONAL sorryAx tripwire below.
        fq_name = f"Problems.{goal['problem']}.{sid_token}"
        v = gateway_lifecycle.verify_file(
            scratch_dest, write_olean=True,
            axioms_for=fq_name, workspace=workspace,
        )
        if "error" in v:
            _rm_scratch()
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
            _rm_scratch()
            return _abort(
                "lake_build_error",
                diagnostics.annotate_failure_detail(
                    err_lines or "(no error diagnostics returned)"),
                leading,
            )
        # Universal sorryAx tripwire — independent of axioms_whitelist. A
        # transitive sorry (cited stub/orphan sibling) compiles green
        # (warning, not error); `#print axioms` is the ground truth.
        # Reject before promoting the scratch (P13 root sorryAx came in
        # via exactly this: a leaf citing an orphan stub).
        if "sorryAx" in (v.get("axioms") or []):
            _rm_scratch()
            return _abort(
                "axiom_violation",
                "leaf-bypass proof term depends on sorryAx — a transitive "
                "sorry (e.g. a cited stub/orphan sibling), not a complete "
                "proof",
                leading,
            )
        if mfst.axioms_whitelist:
            if v.get("axiom_error"):
                _rm_scratch()
                return _abort(
                    "axiom_violation",
                    f"leaf-bypass axiom probe error: {v['axiom_error']}",
                    leading,
                )
            used = set(v.get("axioms") or [])
            rogue = used - set(mfst.axioms_whitelist)
            if rogue:
                _rm_scratch()
                return _abort(
                    "axiom_violation",
                    f"leaf-bypass rogue axioms: {sorted(rogue)}",
                    leading,
                )
        # Race guard mirrors the decomp path's check at line ~666.
        fresh = db.get_goal(conn, goal_id)
        if fresh is None or fresh["status"] not in ("open", "attempting"):
            _rm_scratch()
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
    # Existing goal slugs for this problem — used both to guard #3
    # normalization against silently renaming onto an existing goal and by
    # `_resolve_slug_collisions` below. Computed once (the loop inserts no
    # goals, so it's stable).
    existing_slugs = {
        row["slug"] for row in conn.execute(
            "SELECT slug FROM goals WHERE problem = ?",
            (goal["problem"],),
        ).fetchall()
    }
    sub_meta: list[tuple[str, Path]] = []  # (slug, source_in_attempts)
    norm_renames: dict[str, str] = {}      # raw_slug -> normalized (#3)
    batch_slugs: set[str] = set()          # slugs claimed earlier this batch
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
            # #3 — camelCase / PascalCase is mechanically fixable: normalize
            # to snake_case in place (rewrite decl + rename file, the same
            # surgery the `_2` collision path does) instead of rejecting and
            # burning a retry the agent can't reliably satisfy. Truly
            # un-normalizable (digit start / punctuation / unicode) still
            # rejects as naming_violation.
            norm = _normalize_slug(slug)
            if norm is None:
                return _abort(
                    "naming_violation",
                    f"sub-goal slug {slug!r} must match [a-z][a-z0-9_]* "
                    f"(lowercase ascii start, then ascii/digits/underscore) "
                    f"and is not mechanically normalizable",
                    leading,
                )
            # Refuse to normalize ONTO an existing goal / sibling batch file:
            # that is not a cosmetic fix but a collision the agent must
            # resolve. Silently normalizing + `_2`-suffixing clobbered a real
            # brick with a stale placeholder and produced a confusing "has no
            # <slug> declaration" build error (stokes slice_eventually_zero,
            # agent-feedback 2026-06-13). `_SLUG_RE`-valid originals that
            # collide still fall through to the `_2` resolver — only a
            # NORMALIZATION-created collision is rejected here.
            if norm in existing_slugs or norm in batch_slugs:
                return _abort(
                    "naming_violation",
                    f"sub-goal slug {slug!r} normalizes to {norm!r}, which "
                    f"already names another sub-goal. If you meant that goal, "
                    f"cite it instead of creating a new file; otherwise rename "
                    f"this one to a distinct snake_case slug.",
                    leading,
                )
            new_ns = ns.parent / f"new_{norm}.lean"
            content = ns.read_text(encoding="utf-8")
            content = re.sub(
                rf"\btheorem\s+{re.escape(slug)}\b",
                f"theorem {norm}", content, count=1,
            )
            new_ns.write_text(content, encoding="utf-8")
            if new_ns != ns:
                ns.unlink()
            norm_renames[slug] = norm
            slug, ns = norm, new_ns
        batch_slugs.add(slug)
        sub_meta.append((slug, ns))

    if norm_renames:
        # Point patch.lean at the normalized sub-goal names (word-boundary
        # so substrings of unrelated identifiers stay intact) — the same
        # rewrite the `_2` collision path applies below.
        patch_text = patches[0].read_text(encoding="utf-8")
        for raw, norm in norm_renames.items():
            patch_text = re.sub(rf"\b{re.escape(raw)}\b", norm, patch_text)
        patches[0].write_text(patch_text, encoding="utf-8")

    # #4 — reject a sub-goal that restates a STRICT ANCESTOR on its own
    # chain (circular decomposition: proving X by reducing to X = zero
    # progress). The agent re-derives an ancestor and gives it the same
    # descriptive slug; the `_2` auto-suffix below would otherwise mask it
    # into a fresh goal whose subtree regresses until it hits the retry cap
    # (P13 stokes 4010 vs 3995, 2026-06-13). Cheap name-collision signal,
    # confirmed by a verbatim theorem-head match so a coincidental name
    # reuse for a genuinely different lemma falls through to `_2`. The
    # deeper isDefEq path (dedupe `no_progress`) should also catch this but
    # proved unreliable here — backlog #4. Non-terminal: the agent retries
    # with the corrective hint in retry_context.
    ancestor_slugs = _strict_ancestor_slugs(conn, goal_id)
    for slug, ns in sub_meta:
        anc_path = ancestor_slugs.get(slug)
        if anc_path is None:
            continue
        try:
            cand_head = _theorem_head(ns.read_text(encoding="utf-8"), slug)
            anc_head = _theorem_head(
                (workspace / anc_path).read_text(encoding="utf-8"), slug)
        except OSError:
            continue
        if cand_head is not None and cand_head == anc_head:
            return _abort(
                "circular_decomposition",
                f"sub-goal `{slug}` restates ancestor `{slug}` on its own "
                f"chain verbatim — proving a goal by reducing to itself makes "
                f"no progress. Decompose differently: reduce the dimension, "
                f"strengthen the induction hypothesis, or split off a "
                f"genuinely smaller lemma.",
                leading,
            )

    # T8 / agent_feedback 91-92,110 — convert a declared sub-goal that
    # merely re-states an existing equivalent sibling into a CITATION of
    # that sibling (drop the redundant file + inject its import) rather
    # than `_2`-forking a duplicate that proves the same brick twice and,
    # for a cascade-shelved sibling, could never be re-registered verbatim
    # (forcing the agent to reshape a provable statement to dodge the
    # matcher). The citation gate downstream links / revives / rejects the
    # sibling by status. See `_partition_sibling_reuse` for the rule.
    kept_sub_meta, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem=goal["problem"], goal_id=goal_id, workspace=workspace,
        sub_meta=sub_meta, existing_slugs=existing_slugs,
        ancestor_slugs=ancestor_slugs,
    )
    if dropped:
        for ns in dropped:
            try:
                ns.unlink()
            except OSError:
                pass
        # Inject the sibling imports into patch.lean (idempotent) so the
        # citation gate sees them and `<slug>` resolves to the sibling's
        # decl. Each entry is a full `import` line placed after the last
        # existing import.
        lines = patches[0].read_text(encoding="utf-8").splitlines()
        present = set(lines)
        add = [ln for ln in reuse_imports if ln not in present]
        if add:
            last_imp = max((i for i, ln in enumerate(lines)
                            if ln.startswith("import ")), default=-1)
            for off, ln in enumerate(add):
                lines.insert(last_imp + 1 + off, ln)
            patches[0].write_text("\n".join(lines) + "\n", encoding="utf-8")
        sub_meta = kept_sub_meta

    # Auto-suffix cross-batch collisions (existing_slugs computed above).
    # Helper is pure; we apply the filesystem side effects here based on the
    # returned rename_map.
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

    # No-progress guard: a sub-goal definitionally equal to the goal being
    # decomposed (or one of its still-unproved ancestors) is a self-similar
    # `X ⊢ X` reduction — it can never be aliased (circular) and just spawns
    # another identical goal. Decline-and-RETRY (NOT terminal): re-prompt the
    # same agent to split smaller or prove directly. Root cause of the Jordan
    # intra-problem duplication (13/13 dups were such self-decomposition
    # chains — the dedupe pool never checked the parent goal itself).
    no_progress_hits = [
        (slug, m.goal_id)
        for (slug, _), m in zip(sub_meta, canonical_for)
        if m is not None and m.kind == "no_progress"
    ]
    if no_progress_hits:
        detail = "; ".join(
            f"`{slug}` ≡ goal {gid} ({db.get_goal(conn, gid)['slug']})"
            for slug, gid in no_progress_hits
        )
        return _abort(
            "no_progress",
            f"sub-goal(s) restate an UNPROVED ancestor (or this goal itself): "
            f"{detail}. Can't be cited — that's circular (the ancestor depends "
            f"on this goal); only PROVED matches auto-cite. Give each sub-goal "
            f"new content (proof composes ≥2 proved results, not the ancestor "
            f"re-applied), or prove the goal directly in patch.lean.",
            leading,
        )

    # #2 reuse extraction — a sub-goal that matched a NON-proved in-problem
    # twin (dedupe kind="reuse") becomes a CITATION of that twin instead of
    # a new goal: dropped from the sub-goal lists, recorded as a patch
    # rewrite applied below. The citation gate then auto-links (revives if
    # shelved) the twin — link-and-wait, exactly as an explicit cite. Done
    # AFTER the disproved / no_progress aborts so those fire on the full
    # set.
    sub_meta, canonical_for, reuse_rewrites = _partition_dedupe_reuse(
        conn, problem=goal["problem"], workspace=workspace,
        sub_meta=sub_meta, canonical_for=canonical_for,
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
    inserts_began = False

    def _discard_placed() -> None:
        """Remove the proof files we placed, via the ownership-guarded
        `proof_store` (so a file owned by ANOTHER goal is never deleted). Valid
        only BEFORE the INSERT loop — afterwards the rows are committed and
        files+rows are consistent, so we must NOT unlink (that would create the
        row-without-file drift)."""
        for p in placed:
            try:
                proof_store.remove_proof(
                    conn, workspace,
                    rel_path=p.relative_to(workspace).as_posix(),
                    owner_goal_id=None)
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass

    try:
        # Ownership guard (structural clobber prevention): every sub-goal dest
        # must be free — owned by NO existing goal. A slug collision that
        # `_resolve_slug_collisions` missed (cross-batch / re-decomposition,
        # backlog #84) would otherwise overwrite a live committed stub here and
        # the failure-cleanup `unlink` would delete it → orphan (DB↔file drift).
        # Refuse BEFORE any write so the clobber-then-orphan window cannot open.
        for _slug, _dest in sub_dests:
            try:
                proof_store.assert_writable(
                    conn, _dest.relative_to(workspace).as_posix(),
                    owner_goal_id=None)
            except proof_store.ClobberError as _ce:
                return _abort("subgoal_slug_collision", str(_ce), leading)
        # Place sub-goal files: alias body for dedupe-hits, original
        # content for novel sub-goals. By this point any disproved-kind
        # and no_progress-kind match has aborted via the early-returns
        # above, so a non-None `match` is guaranteed kind="alias".
        def _novel_content(raw: str) -> str:
            """Sub-goal placed for normal dispatch: base imports + Defs
            opens injected so it elaborates standalone."""
            c = _ensure_imports_subgoal(
                raw, problem=goal["problem"], workspace=workspace)
            return manifest.inject_defs_opens(
                c, problem=goal["problem"], workspace=workspace)

        for idx, ((slug, src), (_, dest), match) in enumerate(zip(
            sub_meta, sub_dests, canonical_for,
        )):
            raw = src.read_text(encoding="utf-8")
            if match is not None:
                # Build the alias body on top of import/opens-injected
                # content so the file elaborates standalone (agent
                # `new_<slug>.lean` files often omit `import Mathlib`).
                if match.kind == "library_alias":
                    # A — cross-problem reuse: canonical is a proved
                    # `Library/` decl (no in-DB goal). Delegate via the
                    # fully-qualified name (its namespace isn't open here).
                    alias_content = dedupe.build_alias_content(
                        original_content=_novel_content(raw),
                        canonical_module=match.library_module,
                        canonical_slug=match.library_fqn,
                        apply_expr=f"@{match.library_fqn}",
                    )
                    canonical_label = f"Library {match.library_fqn}"
                else:
                    canonical_id = match.goal_id
                    canonical = db.get_goal(conn, canonical_id)
                    canonical_module = _lean_path_to_module(
                        workspace, workspace / canonical["lean_path"])
                    alias_content = dedupe.build_alias_content(
                        original_content=_novel_content(raw),
                        canonical_module=canonical_module,
                        canonical_slug=canonical["slug"],
                    )
                    canonical_label = f"goal {canonical_id} ({canonical['slug']})"
                proof_store.atomic_write(dest, alias_content)
                # Build-verify the alias before trusting the dedupe probe.
                # The probe (`_batch_provable_via_apply`) elaborates the
                # candidate in a `dedupe_check` namespace WITHOUT the
                # problem's namespace/opens, so problem-local names (e.g.
                # the `E := EuclideanSpace ℝ (Fin 3)` abbrev) resolve
                # differently than in the real file — the probe's verdict
                # can diverge from the real build (BT 2026-05-29 g3410:
                # `rotation_family_avoiding_disjoint_axis` got aliased to
                # the unrelated `endo_finrank_le_one_eq_det_smul`, probe
                # said OK, real `apply @… <;> assumption` failed to unify).
                # rc-based checks alone are unreliable here (lake env lean
                # emits errors with rc=0, fixed separately at b17fec7);
                # the gateway verify returns structured diagnostics so we
                # accept the alias only when it genuinely elaborates.
                from ..lsp import lifecycle as gateway_lifecycle
                av = gateway_lifecycle.verify_file(
                    dest, write_olean=True, workspace=workspace)
                if av.get("ok") and not av.get("error"):
                    print(f"[dedupe] {slug} → {canonical_label} "
                          f"[build-verified]",
                          flush=True)
                else:
                    # Probe false-positive (or infra error): the alias body
                    # does not build. Discard it and fall back to a novel
                    # sub-goal — write original content + dispatch normally.
                    # Clear the match so the downstream INSERT records this
                    # goal 'open' instead of aliasing it 'proved'.
                    why = av.get("error") or "; ".join(
                        d.get("message", "")
                        for d in (av.get("diagnostics") or [])
                        if d.get("severity") == "error"
                    ) or "alias body failed to build"
                    print(f"[dedupe] {slug} → {canonical_label} REJECTED — "
                          f"build-verify failed ({why[:160]}); treating as "
                          f"novel sub-goal",
                          flush=True)
                    canonical_for[idx] = None
                    proof_store.atomic_write(dest, _novel_content(raw))
            else:
                proof_store.atomic_write(dest, _novel_content(raw))
            placed.append(dest)
        proof_store.atomic_write(
            scratch_dest, patches[0].read_text(encoding="utf-8"))
        # Inject Defs.lean opens into the strategy patch as well — the
        # patch carries the strategy body (which may reference `π` /
        # `Real.sin` etc. via Defs's shared notation) and must replay
        # opens for the same reason every other agent-authored file
        # does. See state/manifest.py:inject_defs_opens docstring.
        proof_store.atomic_write(
            scratch_dest,
            manifest.inject_defs_opens(
                scratch_dest.read_text(encoding="utf-8"),
                problem=goal["problem"], workspace=workspace,
            ),
        )
        placed.append(scratch_dest)

        # #2 — rewrite reuse sub-goals into citations of their twin (swap
        # the slug token for the twin's theorem name + inject its import).
        # The citation gate below then auto-links / revives the twin and
        # the strategy waits for it.
        if reuse_rewrites:
            proof_store.atomic_write(
                scratch_dest,
                _apply_reuse_rewrites(
                    scratch_dest.read_text(encoding="utf-8"), reuse_rewrites))

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
        auto_link_ids, revive_ids, cite_err = _resolve_cite_dependencies(
            conn, problem=goal["problem"],
            patch_text=scratch_dest.read_text(encoding="utf-8"),
            declared_slugs=declared_slugs, allow_auto_link=True,
            workspace=workspace,
        )
        if cite_err:
            _discard_placed()
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
            _discard_placed()
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
            _discard_placed()
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
        inserts_began = True            # rows now auto-commit per insert_goal;
        #                                from here a failure must NOT unlink the
        #                                placed files (would orphan the rows).
        for (slug, dest), match in zip(sub_dests, canonical_for):
            stmt = _extract_statement_from_lean(dest)
            rel = dest.relative_to(workspace).as_posix()
            raw = dest.read_text(encoding="utf-8")
            entry_kind = _parse_entry_kind(raw)
            # Directive consumed → DB column is the routing SoT now.
            # Strip the comment from the permanent file so it doesn't
            # linger in proofs/ or propagate into the curated Library on
            # migrate. (stmt already extracted above; downstream reads
            # don't depend on this line.)
            cleaned = _strip_entry_kind(raw)
            if cleaned != raw:
                proof_store.atomic_write(dest, cleaned)
            new_gid = db.insert_goal(
                conn, problem=goal["problem"], slug=slug,
                lean_path=rel, statement=stmt, origin="backward",
                depth=goal["depth"] + 1,
                entry_kind=entry_kind,
            )
            if match is not None:
                # Past the same_as_disproved / no_progress early-returns →
                # kind is "alias" (in-problem) or "library_alias" (A).
                transitions.apply_goal_transition(
                    conn, new_gid, "proved", event="backward_alias_proved")
                if match.kind == "library_alias":
                    # Canonical is a committed Library decl, not an in-DB
                    # goal — no alias_target_id (prune doesn't manage
                    # Library; the proof IS the `apply @<fqn>` body on
                    # disk). The reuse citation is logged at dedupe time.
                    pass
                else:
                    # Record alias relationship so prune retains the
                    # canonical (in case it's an orphan from a dead
                    # strategy) for as long as this alias is alive.
                    db.set_alias_target(conn, new_gid, match.goal_id)
            else:
                ok, msg = _try_promote_sorry_free(
                    dest=dest, problem=goal["problem"], slug=slug,
                    workspace=workspace,
                    axioms_whitelist=mfst.axioms_whitelist,
                )
                if ok:
                    transitions.apply_goal_transition(
                        conn, new_gid, "proved",
                        event="backward_sorryfree_proved")
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
        # Revive cited soft-terminal siblings (shelved / dead) before
        # linking: the strategy_subgoals link below gives each a fresh
        # live path to root through THIS strategy, so flip it back to
        # 'open' for re-dispatch. dedupe does not block these statuses,
        # so neither does this revival (db.py `goals.status` contract;
        # agent_feedback T8 — cascade-shelved leaves were otherwise
        # unreachable forever once cited). Re-check status to skip any
        # the time-of-check/use race already moved.
        for rid in sorted(revive_ids):
            cur = db.get_goal(conn, rid)
            # Only 'shelved' is revivable by citation; 'dead' is rejected
            # at the gate (never reaches revive_ids). Re-check status to
            # skip any the time-of-check/use race already moved to a
            # non-revivable terminal.
            if cur is not None and str(cur["status"]) == "shelved":
                transitions.apply_goal_transition(
                    conn, rid, "open", event="backward_revive")
                print(f"[backward-revive] cited sibling goal {rid} "
                      f"({cur['slug']}) shelved → open", flush=True)
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
        # Cleanup: remove only this strategy's placed files (other strategies
        # untouched), but ONLY if we failed before the INSERT loop began — once
        # `insert_goal` starts auto-committing rows, the rows reference these
        # files, so unlinking would create row-without-file drift. A failure
        # mid-INSERT leaves whatever committed consistent; the rest is an orphan
        # file the `proof_store.inventory` / recovery sweep reconciles.
        if not inserts_began:
            _discard_placed()
        return _abort(
            "lake_build_error",
            diagnostics.annotate_failure_detail(str(exc)),
            leading,
        )
