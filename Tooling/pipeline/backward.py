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
`_strip_entry_kind`, `_resolve_slug_collisions`) live here. Shared
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
from ..state import (assemble, db, metaprog, proof_store, thresholds,
                     transitions)
from ..state import intent as intent_mod
from ..quality import dedupe, diagnostics
from . import _axiom
from . import _presearch
from ._cite_gate import (_PROBLEM_IMPORT_RE, _resolve_cite_dependencies,
                         inject_missing_sibling_imports)  # noqa: F401 — re-export (tests)


# Sub-goal slug pattern: lowercase letter start, then lowercase letters,
# digits, underscore. Length is bounded separately (≤ 60) so the regex
# stays simple. Picked at agent time per `prompts/backward.md` "Write".
# Shared SoT (task #5 Step A) — forward.py and the gateway submission
# mirror import the same object; this was the last literal copy
# (2026-07-04 convention audit, finding 8).
_SLUG_RE = assemble.SLUG_RE


def _place_unowned(conn: sqlite3.Connection, workspace: Path,
                   dst: Path, content: str) -> None:
    """Ownership-guarded placement of a not-yet-owned proof artifact — a fresh
    sub-goal stub (`L_<slug>.lean`, its goal row INSERTed afterwards) or the
    strategy scratch file (`_strategy_s*.lean`, never goal-owned). Routes through
    the chokepoint so a path some OTHER goal already owns raises ClobberError
    before the write, instead of clobbering a committed file (DB↔file drift)."""
    proof_store.place_proof(
        conn, workspace, goal_id=None,
        rel_path=dst.relative_to(workspace).as_posix(), content=content)


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


def _dead_twin_block_reason(conn, problem: str,
                            dead_goal_id: int) -> "str | None":
    """Dead-twin guard verdict for one dedupe kind='dead' hit
    (agent_feedback 2026-07-09/10): None when the problem's proved base
    has GROWN since the twin died — the world changed, a retry with new
    tools is the designed revival path. Otherwise the decline fragment
    carrying the twin's last failure forensics, so the retry / next
    Strategist sees WHY the identical statement already died instead of
    re-walking it blind."""
    twin = db.get_goal(conn, dead_goal_id)
    if twin is None:
        return None
    grown = conn.execute(
        "SELECT 1 FROM goals WHERE problem = ? AND status = 'proved'"
        "  AND updated_at > ? LIMIT 1",
        (problem, str(twin["updated_at"])),
    ).fetchone() is not None
    if grown:
        return None
    prior = conn.execute(
        "SELECT failure_reason, substr(COALESCE(failure_detail,''), 1, 300)"
        "       AS detail FROM dead_attempts"
        " WHERE target_id = ? AND target_kind = 'Goal'"
        " ORDER BY id DESC LIMIT 1", (int(dead_goal_id),),
    ).fetchone()
    why = (f"last failure: {prior['failure_reason']} — {prior['detail']}"
           if prior else "no recorded attempt detail")
    return f"≡ dead goal {int(dead_goal_id)} ({twin['slug']}); {why}"


def _existing_duplicate_strategy(conn, goal_id: int,
                                 linked_set: "set[int]") -> "int | None":
    """The id of an existing 'proposed'/'stalled' strategy on `goal_id`
    whose subgoal set equals `linked_set`, or None. P3 duplicate-strategy
    guard: with the statement-defeq reuse link (P1) live, a walled
    re-decomposition resolves to pure links — if an identical link set
    already exists, committing another strategy row is pure pile-up.
    Only live-ish statuses count: a dead/superseded twin does not block
    a fresh assertion of the same structure."""
    if not linked_set:
        return None
    by_sid: "dict[int, set[int]]" = {}
    for r in conn.execute(
        "SELECT s.id AS sid, ss.subgoal_id AS gid FROM strategies s"
        " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        " WHERE s.goal_id = ? AND s.status IN ('proposed','stalled')",
        (int(goal_id),),
    ):
        by_sid.setdefault(int(r["sid"]), set()).add(int(r["gid"]))
    for sid in sorted(by_sid):
        if by_sid[sid] == linked_set:
            return sid
    return None


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


def _strict_ancestor_ids(conn, goal_id: int) -> "set[int]":
    """Goal ids of every STRICT ancestor of `goal_id` (same walk as
    `_strict_ancestor_slugs`, id form). Used by the ancestor-link guard:
    linking an ancestor as a sub-goal closes a strategy-level cycle —
    every strategy on the loop waits for the next and none can ever
    complete (PutnamCmp a5 live deadlock, 2026-07-19). Content guards
    (restatement / defeq) never see this: the statements all differ;
    only the graph knows."""
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
        "SELECT id FROM ancestors",
        (goal_id,),
    ).fetchall()
    return {int(r["id"]) for r in rows} - {int(goal_id)}


def _cited_dependency_guards(
    conn, workspace: Path, *, problem: str, goal_id: int,
    auto_link_ids: "set[int]",
) -> "tuple[str, str] | None":
    """Guards on AUTO-LINKED cited siblings (goals this patch imports that
    are not yet proved). Returns (failure_reason, detail) or None.

    Citation permission is shape-derived (task #123): any patch that cites
    an unproved sibling registers a `strategy_subgoals` wait edge and
    defers verification, whether or not it also declares stubs. Both
    guards below therefore have to run on BOTH commit paths — before, the
    structural one lived only in the decomposition branch because the
    leaf-bypass branch could not cite an unproved sibling at all.

      * structural — the cited goal is an ANCESTOR: the strategies would
        wait on each other forever.
      * semantic — the cited goal is definitionally equal to this goal
        or to an unproved ancestor: `X ⊢ X`, no progress. Mirrors the
        `no_progress` verdict declared sub-goals already get; only a
        PROVED match is a legitimate citation of an equal statement.
    """
    if not auto_link_ids:
        return None
    cyc = sorted(set(auto_link_ids) & _strict_ancestor_ids(conn, goal_id))
    if cyc:
        names = []
        for _gid in cyc:
            _g = db.get_goal(conn, _gid)
            names.append(str(_g["slug"]) if _g else f"goal {_gid}")
        return (
            "circular_decomposition",
            f"citing {', '.join(names)} closes a dependency cycle — it is "
            f"an ANCESTOR of this goal (this goal is part of ITS proof, so "
            f"it cannot also prove this goal; the strategies would wait on "
            f"each other forever). Cite a goal from elsewhere in the tree, "
            f"or decompose into genuinely smaller NEW pieces.",
        )
    # Semantic probe — read each cited sibling's committed statement file
    # and run it through the same dedupe batch declared sub-goals use.
    candidates: "list[tuple[str, str]]" = []
    gids: "list[int]" = []
    for gid in sorted(auto_link_ids):
        g = db.get_goal(conn, gid)
        if g is None:
            continue
        try:
            text = (workspace / str(g["lean_path"])).read_text(
                encoding="utf-8")
        except OSError:
            continue
        candidates.append((str(g["slug"]), text))
        gids.append(gid)
    if not candidates:
        return None
    from ..quality import dedupe as _dedupe
    matches = _dedupe.find_canonicals_batch(
        conn, workspace, problem=problem, parent_goal_id=goal_id,
        candidates=candidates)
    hits = [(candidates[i][0], gids[i])
            for i, m in enumerate(matches)
            if m is not None and m.kind == "no_progress"]
    if hits:
        detail = "; ".join(f"`{slug}` (goal {gid})" for slug, gid in hits)
        return (
            "no_progress",
            f"cited sibling(s) restate this goal or an UNPROVED ancestor: "
            f"{detail}. Waiting on a statement equal to your own is not a "
            f"proof step — it just parks this goal behind an identical one. "
            f"Cite a strictly weaker result, or prove the goal directly.",
        )
    return None


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
        if str(sib["status"]) in transitions.GOAL_FAILED_TERMINALS:
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
    """Single impl lives in `state.assemble.ensure_framework_imports` (task
    #5 Step A — the gateway's validate path runs the SAME function, so the
    two sides can no longer drift). Kept under the historical name for the
    existing call sites and tests."""
    from ..state import assemble
    return assemble.ensure_framework_imports(
        content, problem=problem, workspace=workspace)


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
    attempts_dir: "Path | None" = None,
) -> tuple[bool, str]:
    """If `dest` is sorry-free AND its `#print axioms` set ⊆ whitelist,
    return (True, msg). Otherwise (False, reason).

    The strategy's batch lake build at the caller's site already
    confirmed the file compiles, so the literal `\\bsorry\\b` substring
    check is the cheap pre-filter; the real authority is `axiom_probe`.
    `attempts_dir` routes the probe to the pipeline's OWN slot
    (pipeline=slot rule) — this runs inside Backward's commit loop while
    the session is still held; a borrow would evict another tenant.
    """
    try:
        content = dest.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"
    if _SORRY_RE.search(content):
        return False, "body contains sorry"
    return _axiom.axiom_probe_file(
        workspace, dest, problem=problem, slug=slug,
        whitelist=axioms_whitelist, attempts_dir=attempts_dir,
    )


# Legacy `-- entry_kind:` directive line (routing retired v33 — the
# Formalizer decides prove-vs-split itself). The strip survives so a
# legacy-shaped stub's directive comment doesn't linger in proofs/ or
# propagate into the curated Library on migrate.
_ENTRY_KIND_LINE_RE = re.compile(
    r"(?m)^[ \t]*--[ \t]*entry_kind[ \t]*:[ \t]*(?:Builder|Backward)\b.*\r?\n?"
)


def _strip_entry_kind(lean_text: str) -> str:
    """Remove any legacy `-- entry_kind:` directive line(s) (dead
    residue post-v33; rationale comments on their own `--` lines are
    untouched)."""
    return _ENTRY_KIND_LINE_RE.sub("", lean_text)


# ---------------------------------------------------------------------
# Pipeline entry
# ---------------------------------------------------------------------

def run_backward(conn: sqlite3.Connection, *, goal_id: int,
                 workspace: Path, intent: intent_mod.ProblemIntent,
                 pipeline_id: str,
                 decision_id: int | None = None,
                 ) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner Backward then persists or clears
    the partial-output draft so a future spawn on this same goal sees
    the in-flight PROPOSAL.md from the prior failed/timed-out attempt
    instead of starting from scratch.

    Phase 2 — `decision_id` flows from the spawning queue row (non-NULL
    only when a Strategist Inject decision emitted this entry). Passed
    through to `compile_context` for `## The argument for this brick`.

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
                                 intent=intent, pipeline_id=pipeline_id,
                                 decision_id=decision_id)
    if (result.outcome in ("success", "moot")
            or result.failure_reason == "goal_no_longer_open"):
        _drafts.clear_partial(problem_dir=problem_dir, kind="backward",
                              goal_id=goal_id)
        _drafts.clear_partial_patch(problem_dir=problem_dir, kind="backward",
                                    goal_id=goal_id)
    else:
        attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
        note = _drafts.persist_partials(attempts_dir=attempts_dir,
                                        problem_dir=problem_dir,
                                        kind="backward", goal_id=goal_id,
                                        conn=conn)
        if note is None:
            # Even the postmortem left nothing — save the half-finished
            # patch as the only remaining clue (user ruling: note is
            # preferred, patch is the no-note fallback).
            _drafts.salvage_patch_fallback(
                attempts_dir=attempts_dir, problem_dir=problem_dir,
                kind="backward", goal_id=goal_id)
    return result


def _run_backward_inner(conn: sqlite3.Connection, *, goal_id: int,
                        workspace: Path, intent: intent_mod.ProblemIntent,
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
        _build_strategy_skeleton,
        _extract_decline_reason, _extract_leading_comments,
        _extract_statement_from_lean, _grep_forbidden,
        _inject_imports_for_subs, _is_sorry_stub,
        _lean_path_to_module, _normalize_signature,
        _live_stubs, _safe_glob, _signature_prefix,
        _slug_from_filename,
        DECLINE_TO_FAILURE_REASON,
    )
    from ._retry import SpawnCtx, run_lsp_edit_loop
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
    if skeleton is None and re.search(r"\bsorry\b", parent_text):
        # decl-#2 — inferred-type def stub: the source spells no type
        # colon, but the declInfo oracle's ppSignature makes the
        # elaborator's type explicit. Reconstruct the skeleton from it,
        # then BUILD-VALIDATE before trusting: a pp form that doesn't
        # re-elaborate would become a locked signature the agent can
        # neither satisfy nor change (a whole-spawn burn, the exact
        # class this dissolves). The sorry guard keeps promoted-alias
        # parents (`def g := @ns.sN`, sorry-free) on the clean abort
        # path — that goal is proved; a sibling raced us.
        from ..lsp.decl_oracle import DeclOracle
        oracle = DeclOracle.cached_for_file(
            parent_abs_for_skeleton, workspace=workspace)
        d = oracle.find(goal["slug"]) if oracle is not None else None
        if d is not None:
            candidate = _build_strategy_skeleton(
                parent_text, parent_slug=goal["slug"],
                sid_token=sid_token, namespace=namespace,
                oracle_sig=d.signature)
            if candidate is not None:
                probe = attempts_dir / "_skeleton_probe.lean"
                probe.parent.mkdir(parents=True, exist_ok=True)
                probe.write_text(candidate, encoding="utf-8")
                pv = _axiom.verify_on_own_slot(
                    probe, workspace=workspace, attempts_dir=attempts_dir,
                    write_olean=False)
                if pv.get("ok") and not pv.get("error"):
                    skeleton = candidate
                    print(f"[backward] g{goal_id} {goal['slug']}: skeleton "
                          f"reconstructed from ppSignature (source has no "
                          f"type ascription)", flush=True)
                else:
                    print(f"[backward] g{goal_id} {goal['slug']}: "
                          f"ppSignature skeleton failed to elaborate — "
                          f"falling back to not-decomposable "
                          f"({str(pv.get('error') or 'diagnostics')[:120]})",
                          flush=True)
    if skeleton is None:
        transitions.apply_strategy_transition(
            conn, strategy_id, "dead", event="skeleton_failed")
        return PipelineResult(
            outcome="failed",
            failure_reason="parent_stub_not_decomposable",
            failure_detail=(
                f"no decomposable `<kind> {goal['slug']} ... : <type>` head "
                f"in {goal['lean_path']} — either the declaration is absent "
                f"(may have been promoted by a sibling already) or it has "
                f"no top-level type colon (inferred-type def / promoted "
                f"alias) and the declInfo oracle could not reconstruct a "
                f"buildable signature"
            ),
        )
    skeleton_signature = _normalize_signature(
        _signature_prefix(skeleton, sid_token))
    # D-lite (task #5): persist the locked signature so the gateway's
    # validate_file can pre-announce the commit-time signature gate — the
    # agent otherwise only learns "you edited the locked signature" at
    # commit (validate elaborates an equivalent rewrite just fine). The
    # attempts dir survives warm retries and is rmtree'd by WorkArea.
    try:
        (attempts_dir / "_locked_signature.txt").write_text(
            skeleton_signature, encoding="utf-8")
    except OSError:
        pass                                  # best-effort — probe-side only

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

    def backward_cold_prep(ctx: SpawnCtx) -> None:
        # Cold start (and fresh-rescue, which is also cold-with-fresh-
        # sid): agent has no session memory to resume. Compile
        # Context.md fresh and write the strategy skeleton so the agent's
        # first Read of patch.lean shows a clean `theorem s<sid_token>
        # ... := by sorry` template. For fresh-rescue, the helper has
        # already written `_prior_analysis.md` to attempts_dir; the
        # cold prompt's `is_fresh_rescue` flag injects a Read directive
        # so the agent consumes it before any other action.
        # Warm retries skip this (run_lsp_edit_loop calls it cold-only) —
        # agent's --resume picks up Context from the prior turn, and
        # patch.lean keeps whatever the agent wrote last iteration so
        # retry_context-driven fixes can be incremental.
        # target-1: per-node pre-search (once per node, cached) before the
        # context is compiled, so its candidate-lemma section is present.
        _presearch.ensure_presearch(
            goal=goal, workspace=workspace, problem_dir=problem_dir,
            attempts_dir=ctx.attempts_dir, prompt_dir=PROMPT_DIR,
            conn=conn)
        context.compile_context(conn, goal=goal, intent=intent,
                              attempts_dir=ctx.attempts_dir,
                              strategy_id=strategy_id,
                              kind="backward",
                              decision_id=decision_id)
        (ctx.attempts_dir / "patch.lean").write_text(
            skeleton, encoding="utf-8")

    def backward_parse() -> "PipelineResult":  # noqa: F821
        # No goal_lean restore needed — agent's apply_edit targets
        # patch.lean (sandboxed in attempts_dir), so goal_lean is
        # never mutated during the spawn. Parse reads patch.lean +
        # new_*.lean from attempts_dir; the only writer of goal_lean
        # is verify_housekeeping's promote_to_alias (main thread).
        return _backward_parse_and_commit(
            conn=conn, goal=goal, goal_id=goal_id, intent=intent,
            workspace=workspace, attempts_dir=attempts_dir,
            strategy_id=strategy_id, sid_token=sid_token,
            skeleton_signature=skeleton_signature,
        )

    from ._hooks import make_goal_hooks
    (backward_postmortem, backward_reflection,
     backward_feedback, backward_death) = make_goal_hooks(
        # label `backward`; the work spawn below is dispatched as
        # `formalizer`, and the tail turns resume ITS session.
        kind="backward", seat="formalizer",
        goal=goal, problem_dir=problem_dir,
        attempts_dir=attempts_dir, prompt_dir=PROMPT_DIR,
        workspace=workspace,
        postmortem_prompt=PROMPT_DIR / "backward" / "backward_postmortem.md")

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
    # Provider-level infra set from the one registry (task #5 — this was
    # the byte-identical private copy that outlived _infra.py's
    # centralization).
    from ..state.failures import PROVIDER_INFRA_REASONS as _INFRA_REASONS

    # ── Phase 0: deterministic tactic_try (Builder Phase 1, ported) ──
    # The `hint` pre-pass survives the Builder retirement: a zero-spawn
    # close for register_hint-level goals, now riding the strategy frame
    # so success goes through the SAME parse/commit gates (annotation,
    # forbidden grep, leaf-bypass axiom probe) as every agent patch.
    # First dispatch only — `hint`'s register_hint set is deterministic.
    # Any failure in this block falls through to the staged flow.
    if int(goal["attempts"]) == 0:
        from . import _parse_hint_winner, _replace_proof_body
        try:
            probe_path = attempts_dir / "_hint_probe.lean"
            probe_path.parent.mkdir(parents=True, exist_ok=True)
            probe_path.write_text(
                _replace_proof_body(skeleton, "hint"), encoding="utf-8")
            pv = _axiom.verify_on_own_slot(
                probe_path, workspace=workspace, attempts_dir=attempts_dir,
                write_olean=False)
            winner: "str | None" = None
            if pv.get("ok") and not pv.get("error"):
                for d in pv.get("diagnostics") or []:
                    if d.get("severity") == "info":
                        w = _parse_hint_winner(d.get("message", ""))
                        if w:
                            winner = w
                            break
            if winner is not None:
                (attempts_dir / "patch.lean").write_text(
                    f"-- hint: closed by deterministic tactic_try "
                    f"(`{winner}`)\n"
                    + _replace_proof_body(skeleton, winner),
                    encoding="utf-8")
                hint_result = _backward_parse_and_commit(
                    conn=conn, goal=goal, goal_id=goal_id, intent=intent,
                    workspace=workspace, attempts_dir=attempts_dir,
                    strategy_id=strategy_id, sid_token=sid_token,
                    skeleton_signature=skeleton_signature,
                )
                if hint_result.outcome in ("proved", "success"):
                    print(f"[hint] g{goal_id} {goal['slug']}: closed by "
                          f"`{winner}` — no spawn", flush=True)
                    return hint_result
                # Winner didn't survive the commit gates — fall through.
        except Exception as exc:  # noqa: BLE001 — pre-pass is best-effort
            print(f"[hint] g{goal_id} {goal['slug']}: tactic_try pre-pass "
                  f"errored, skipped ({exc})", flush=True)
            # Residue sweep (review 07-27): a raise inside the commit
            # attempt can leave an unowned proofs/_strategy_s<N>.lean
            # (inert — never imported or citable — but drift noise).
            try:
                _row = conn.execute(
                    "SELECT scratch_path FROM strategies WHERE id=?",
                    (strategy_id,)).fetchone()
                if _row is not None and not _row["scratch_path"]:
                    (problem_dir / "proofs"
                     / f"_strategy_{sid_token}.lean").unlink(missing_ok=True)
            except Exception:  # noqa: BLE001
                pass

    # ── Intake stage (update_plan_2026_07 #1) ─────────────────────────
    # A short first turn on a fresh session judges the assignment against
    # the Programme ## Proof before any Lean work. Its decline is the
    # cheapest exit (no presearch, no work spawn); any intake malfunction
    # degrades to the classic single-turn cold flow (initial_sid=None).
    # Context for the intake turn deliberately predates presearch — a
    # declined goal must not pay the search; after `proceed`, presearch
    # runs and Context.md is recompiled with the candidate section.
    from . import _stages

    def _compile_ctx() -> None:
        context.compile_context(conn, goal=goal, intent=intent,
                                attempts_dir=attempts_dir,
                                strategy_id=strategy_id,
                                kind="backward",
                                decision_id=decision_id)

    def _moot_guard() -> "PipelineResult | None":
        # Mirror the retry helper's pre-loop budget check so an
        # over-budget goal (BFS dispatch race) exits before the intake
        # spawn spends anything. Inject-driven dispatches carry a fresh
        # budget (decision_id) and skip this.
        if decision_id is not None:
            return None
        if (thresholds.SHELVE_THRESHOLD - int(goal["attempts"])) > 0:
            return None
        print(f"[retry-moot] g{goal_id} pre-intake: attempts="
              f"{int(goal['attempts'])} >= shelve_threshold="
              f"{thresholds.SHELVE_THRESHOLD}; status={goal['status']}",
              flush=True)
        return PipelineResult(outcome="moot")

    result, intake_sid = _stages.run_prework(
        _stages.Arm(
            label=f"g{goal_id} {goal['slug']}",
            compile_context=_compile_ctx,
            seed=lambda: (attempts_dir / "patch.lean").write_text(
                skeleton, encoding="utf-8"),
            presearch=lambda: _presearch.ensure_presearch(
                goal=goal, workspace=workspace, problem_dir=problem_dir,
                attempts_dir=attempts_dir, prompt_dir=PROMPT_DIR, conn=conn),
            # Goal-arm declines drive the cascade, so they keep their own
            # reason vocabulary (the mint arm renders the Forward shape).
            decline_result=lambda reason, note: PipelineResult(
                outcome="failed",
                failure_reason=DECLINE_TO_FAILURE_REASON.get(reason, reason),
                failure_detail=f"intake decline: {note}"),
            pre_intake_guard=_moot_guard,
        ),
        prompt_dir=PROMPT_DIR, attempts_dir=attempts_dir,
        problem_dir=problem_dir, workspace=workspace)

    try:
        # Task #8: Backward was the last pipeline hand-rolling the spawn
        # ceremony (register + mcp-config + spawn_llm closure) that
        # run_lsp_edit_loop exists to own. Same semantics: cold spawns run
        # backward_cold_prep, the loop targets attempts_dir/patch.lean.
        # Formalizer: the first work spawn resumes the intake session
        # (initial_sid) with the work-stage prompt; a stale/degraded
        # intake session falls back to the classic cold path.
        if result is None:
            result = run_lsp_edit_loop(
                conn=conn,
                goal_id=goal_id,
                pipeline_id=pipeline_id,
                budget_threshold=thresholds.SHELVE_THRESHOLD,
                shelve_threshold=thresholds.SHELVE_THRESHOLD,
                attempts_dir=attempts_dir,
                workspace=workspace,
                problem=str(goal["problem"]),
                problem_dir=problem_dir,
                kind="formalizer",
                prompt_path=PROMPT_DIR / "formalizer" / "formalize.md",
                target=attempts_dir / "patch.lean",
                cold_prep_fn=backward_cold_prep,
                parse_fn=backward_parse,
                postmortem_fn=backward_postmortem,
                reflection_fn=backward_reflection,
                feedback_fn=backward_feedback,
                death_fn=backward_death,
                decision_id=decision_id,
                initial_sid=intake_sid,
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
    *, conn, goal, goal_id, intent, workspace, attempts_dir,
    strategy_id, sid_token, skeleton_signature,
) -> "PipelineResult":  # noqa: F821
    """Parse + dedupe + place + build + commit pass for one Backward
    spawn. Called by the in-pipeline retry helper after a successful
    spawn (rc=0). Returns 'success' on commit, 'failed' on any
    structural / build problem; the caller decides whether to retry
    (helper) or escalate (cascade).

    Strategy mark-dead cleanup is the OUTER caller's responsibility —
    this function leaves the strategy at 'proposed' even on failure
    so warm retries can run against the same row.

    (Task #8: the former 13-helper dependency-injection signature —
    an import-avoidance workaround — is gone; the helpers are ordinary
    package imports below, same objects the caller passed.)
    """
    from . import (
        PipelineResult,
        _extract_decline_reason, _extract_leading_comments,
        _extract_statement_from_lean, _grep_forbidden,
        _inject_imports_for_subs, _is_sorry_stub,
        _lean_path_to_module, _normalize_signature,
        _live_stubs, _safe_glob, _signature_prefix,
        _slug_from_filename,
        DECLINE_TO_FAILURE_REASON,
    )
    from ..state.assemble import strip_annotation_placeholder

    def _abort(reason: str, detail: str = "",
               proposal_md: str = "") -> "PipelineResult":
        return PipelineResult(
            outcome="failed", failure_reason=reason,
            failure_detail=detail, proposal_md=proposal_md,
        )

    # Verify freshly-placed files on THIS pipeline's OWN claimed slot
    # (verify_in_session) rather than borrowing a free slot (verify_file).
    # The pipeline's gateway session is still alive here — it's released only
    # at WorkArea teardown, after this commit — so the slot it claimed at
    # register_session is ours to use for the whole lifecycle. Borrowing
    # instead evicts an actively-claimed slot whose prior elaboration may
    # still be flushing diagnostics; the (version-blind) diagnostics cache
    # then surfaces that tenant's stale error against our clean stub — a
    # spurious `lake_build_error: <stub>:L:C expected token` on a file that
    # builds clean (root-caused 2026-06-29; only fires on decomposition,
    # which is exactly when this gate runs). Our own slot has no concurrent
    # foreign tenant, so no cross-talk.
    def _verify_owned(path, *, write_olean=True, axioms_for=None,
                      decl_info=False):
        # Delegates to the shared pipeline=slot dispatch (single impl of
        # "own slot when the session token is present, borrow only as
        # defensive fallback").
        return _axiom.verify_on_own_slot(
            path, workspace=workspace, attempts_dir=attempts_dir,
            write_olean=write_olean, axioms_for=axioms_for,
            decl_info=decl_info)

    patches = _safe_glob(attempts_dir, "patch*.lean")
    if not patches:
        return _abort("parse_proposal_fail", "no patch.lean")
    main_patch_text = patches[0].read_text(encoding="utf-8")

    # Metaprogramming gate — FIRST, over patch + every sub-goal stub, and
    # ahead of every other verdict: elaboration-time code runs with the
    # framework's privileges, so a file carrying it must not be read as a
    # decline, an annotation or a signature either. Shares one scanner
    # with the gateway (`state.metaprog`), which already blocked this
    # in-session; reaching here means the text arrived some other way
    # (Write/Edit straight to disk, no LSP tool call).
    for _f in [patches[0]] + _safe_glob(attempts_dir, "new_*.lean"):
        try:
            _text = _f.read_text(encoding="utf-8")
        except OSError:
            continue
        _tok = metaprog.scan_metaprogramming(_text)
        if _tok is not None:
            return _abort("forbidden_metaprogramming",
                          metaprog.blocked_detail(_tok, where=_f.name))

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
            # The seeded placeholder is not the agent's comment — strip
            # it or a bailed skeleton reads as "has leading comments"
            # and the bail discriminator never fires.
            bail_leading = strip_annotation_placeholder(
                _extract_leading_comments(main_patch_text))
            bail_new_subs = _live_stubs(attempts_dir)
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
    # The seed skeleton carries a `-- STRATEGY: replace me` placeholder;
    # an unreplaced one is missing metadata, not documentation. Strip it
    # FIRST so every consumer (decline proposal_md, the emptiness gate,
    # goal-annotation propagation) sees only what the agent wrote.
    leading = strip_annotation_placeholder(
        _extract_leading_comments(main_patch_text))
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

    # EMPTY OUTPUT before the annotation gate (autopsy 2026-08-24: this
    # check sat behind it, so a formalizer that produced NOTHING was
    # booked as an annotation failure — the ~50-count inflation). sorry
    # body + no sub-goal files + no decline = nothing was delivered.
    new_subs = _live_stubs(attempts_dir)
    if not new_subs and _is_sorry_stub(main_patch_text):
        return _abort(
            "parse_proposal_fail",
            "patch=1 new=0 with sorry body and no decline directive; "
            "need decomposition (new_*.lean), a leaf-style proof, or "
            "a `-- decline:` directive.",
            leading,
        )

    if not leading.strip():
        return _abort(
            "agent_no_annotation",
            "patch.lean present but had no comment block before the "
            "first declaration; replace the `-- STRATEGY:` placeholder "
            "above the theorem with your rationale (`--` lines or a "
            "`/- … -/` block; an unreplaced placeholder does not "
            "count) — it is required for goal annotation propagation.",
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

    if not new_subs:
        # Phase 6.5 — Backward leaf-bypass salvage. Mirrors
        # `_try_promote_sorry_free` at the sub-goal level: when the
        # agent over-delivers (writes patch.lean with a complete proof
        # body and no decomposition), the framework registers a
        # 0-subgoal strategy rather than thrashing with parse_proposal_
        # fail. Verify housekeeping picks it up next tick (lake build
        # the patch + promote_to_alias parent → goal proved). (The
        # sorry-body empty-output case aborts ABOVE the annotation
        # gate since 2026-08-24.)
        forbidden = _grep_forbidden(main_patch_text, intent.forbidden_lemmas)
        if forbidden:
            return _abort("forbidden_lemma", forbidden, leading)
        # Citation gate. Shape-derived since task #123: a stub-less patch
        # may cite an unproved sibling too — the soundness guarantee was
        # never the stub declaration, it is the `strategy_subgoals` WAIT
        # edge (verification defers until the cited goal proves). So this
        # path auto-links as well, and the branch below routes on whether
        # the patch actually carries unproved dependencies rather than on
        # whether the agent happened to declare a stub.
        auto_link_ids, revive_ids, cite_err = _resolve_cite_dependencies(
            conn, problem=goal["problem"], patch_text=main_patch_text,
            declared_slugs=set(), allow_auto_link=True,
            workspace=workspace,
        )
        if cite_err:
            return _abort("cite_unproved_sibling", cite_err, leading)
        if auto_link_ids:
            guard = _cited_dependency_guards(
                conn, workspace, problem=goal["problem"], goal_id=goal_id,
                auto_link_ids=set(auto_link_ids))
            if guard is not None:
                return _abort(guard[0], guard[1], leading)
            # A cite-only patch that links exactly what an existing
            # strategy on this goal already waits on adds nothing — same
            # rationale as the decomposition path's twin guard.
            dup_sid = _existing_duplicate_strategy(
                conn, goal_id, set(auto_link_ids))
            if dup_sid is not None:
                return _abort(
                    "duplicate_strategy",
                    f"this patch declares no sub-goal and waits on exactly "
                    f"the same goal set {sorted(auto_link_ids)} as existing "
                    f"strategy s{dup_sid} on this goal — s{dup_sid} is "
                    f"already waiting on those gates. Nothing new will "
                    f"happen that is not already pending.",
                    leading,
                )
        proofs_dir = db.problem_dir(workspace, goal["problem"]) / "proofs"
        proofs_dir.mkdir(parents=True, exist_ok=True)
        scratch_dest = proofs_dir / f"_strategy_{sid_token}.lean"

        def _rm_scratch() -> None:
            proof_store.remove_proof(
                conn, workspace,
                rel_path=scratch_dest.relative_to(workspace).as_posix(),
                owner_goal_id=None)

        # Normalize through the SAME `assemble_for_commit` every other
        # commit path runs (#179, 2026-08-10).
        #
        # This line used to call `intent_mod.inject_defs_opens` — step 3 of
        # five, hand-picked. The comment it replaces recorded the previous
        # instance of exactly this bug: Defs opens were missing here while
        # "the decomposition path below already does this", so a bare
        # Library cite went green in the probe and `Unknown identifier` in
        # lake (currents_boundary_zero, 2026-06-28). That was fixed by
        # adding the one missing step rather than by routing through the
        # one function, which left steps 1, 2, 4 and 5 still missing — and
        # step 5, proved-sibling imports, is #179: a leaf-bypass patch
        # citing a proved sibling elaborated fine in the sandbox (which
        # pre-loads sibling stubs) and failed the real build.
        #
        # 37 agent reports read that failure as "sibling not found" and
        # doubted their own mathematics. The cost of the class is not the
        # rebuild; it is the abandoned line of attack.
        #
        # `declared_slugs` is empty by construction: leaf-bypass declares
        # no sub-goals — that is what makes it leaf-bypass.
        _asm_leaf = assemble.assemble_for_commit(
            patches[0].read_text(encoding="utf-8"),
            problem=goal["problem"], workspace=workspace, conn=conn)
        if _asm_leaf.injected_sibling_imports:
            print(f"[cite] leaf-bypass auto-imported "
                  f"{len(_asm_leaf.injected_sibling_imports)} proved "
                  f"sibling(s): "
                  f"{', '.join(_asm_leaf.injected_sibling_imports)}",
                  flush=True)
        _place_unowned(conn, workspace, scratch_dest, _asm_leaf.text)
        # Verify-unification: gateway worker pool elaborates the
        # strategy file AND writes its olean to disk in one round trip.
        # The olean is needed downstream by `verify_strategy`, which
        # later builds the parent alias against this strategy module.
        # Single-file verify (no cross-module deps within the strategy
        # itself; it imports Mathlib + Defs, both already warm in every
        # slot).
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
        # The single soundness gate (shared with Forward + Builder,
        # `_axiom.axiom_gate`): elaborate the promoted scratch on THIS
        # pipeline's own warm slot (via its session token), request the axiom
        # set, and apply the unconditional sorryAx tripwire + whitelist check
        # — before the leaf-bypass promotes the goal proved. (P13 root sorryAx
        # came in via a leaf citing an orphan stub; a `\bsorry\b` scan can't
        # see that, `collectAxioms` can.)
        # A patch that WAITS (cites an unproved sibling) is exempt from the
        # submit-time probe for the same reason a decomposition patch is:
        # the probe cannot separate this strategy's own sorry from the
        # sorry it legitimately imports from a not-yet-proved dependency
        # (verify.py module docstring). Soundness for that shape is the
        # root-level `axiom_probe` + bisect + rollback backstop, reached
        # only after every wait edge resolves to 'proved'. A patch with no
        # unproved dependency keeps the immediate gate — it goes straight
        # to ready_for_verify, so this is its only check.
        fq_name = f"Problems.{goal['problem']}.{sid_token}"
        if auto_link_ids:
            v = _verify_owned(scratch_dest, write_olean=True)
            if "error" in v:
                _rm_scratch()
                # The reason used to be `lake_build_error` while the
                # detail said "verify infra error" in the same
                # expression — so the row burned a goal attempt and told
                # the agent its Lean was broken (08-12, g7553).
                from ..state.failures import verify_error_reason
                return _abort(
                    verify_error_reason(v) or "lake_build_error",
                    diagnostics.annotate_failure_detail(
                        f"verify infra error: {v['error']}"),
                    leading)
            if not v.get("ok"):
                _rm_scratch()
                err_lines = "\n".join(
                    f"{scratch_dest.name}:{d.get('line','?')}:"
                    f"{d.get('col','?')}  {d.get('message','')}"
                    for d in (v.get("diagnostics") or [])
                    if d.get("severity") == "error")
                if not err_lines:
                    # Same split as the decomposition arm: ok=false with
                    # zero error diagnostics is a worker-side failure
                    # shape, not a Lean verdict.
                    return _abort(
                        "framework_verify_error",
                        f"verify returned ok=false with no error "
                        f"diagnostics on {scratch_dest.name} — a "
                        f"worker-side failure, not a Lean verdict",
                        leading)
                return _abort(
                    "lake_build_error",
                    diagnostics.annotate_failure_detail(err_lines),
                    leading)
        else:
            from ._axiom import axiom_gate
            gate = axiom_gate(
                scratch_dest, fq_name=fq_name,
                whitelist=intent_mod.effective_axioms(
                    intent, problem=goal["problem"]),
                workspace=workspace, attempts_dir=attempts_dir,
                write_olean=True)
            if not gate.ok:
                _rm_scratch()
                detail = gate.detail or ""
                if gate.failure_reason == "lake_build_error":
                    detail = diagnostics.annotate_failure_detail(detail)
                return _abort(gate.failure_reason, detail, leading)
        # Race guard mirrors the decomp path's check at line ~666.
        fresh = db.get_goal(conn, goal_id)
        if fresh is None or fresh["status"] not in ("open", "attempting"):
            _rm_scratch()
            current = fresh["status"] if fresh else "missing"
            return _abort(
                "goal_no_longer_open",
                f"goal {goal_id} transitioned to {current!r} during this "
                f"Backward's stub-less run; aborting to avoid orphan strategy.",
                leading,
            )
        # Revive cited soft terminals, then register the wait edges. Same
        # semantics as the decomposition path — `strategies_ready_for_verify`
        # blocks this strategy until every cited goal proves.
        for rid in sorted(revive_ids):
            cur = db.get_goal(conn, rid)
            if cur is not None and str(cur["status"]) == "shelved":
                transitions.apply_goal_transition(
                    conn, rid, "open", event="backward_revive")
                print(f"[backward-revive] cited sibling goal {rid} "
                      f"({cur['slug']}) shelved → open", flush=True)
        for pos, auto_gid in enumerate(sorted(auto_link_ids)):
            db.link_subgoal(conn, strategy_id=strategy_id,
                            subgoal_id=auto_gid, position=pos)
        scratch_rel = scratch_dest.relative_to(workspace).as_posix()
        db.update_strategy_scratch_path(conn, strategy_id, scratch_rel)
        conn.execute("UPDATE strategies SET proposal_md = ? WHERE id = ?",
                     (leading, strategy_id))
        conn.commit()
        if auto_link_ids:
            print(f"[backward cite-wait] strategy={sid_token} waits on "
                  f"{sorted(auto_link_ids)}", flush=True)
        else:
            print(f"[backward leaf-bypass] strategy={sid_token} → "
                  f"ready_for_verify", flush=True)
        return PipelineResult(outcome="success", proposal_md=leading)

    # Forbidden-lemma grep covers patch + every sub-goal stub.
    all_text = "\n".join([main_patch_text] +
                          [p.read_text(encoding="utf-8") for p in new_subs])
    forbidden = _grep_forbidden(all_text, intent.forbidden_lemmas)
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
                f"redundant during your decomposition, withdraw it with "
                f"`withdraw_stub(slug=\"{slug}\")` — the old wording said "
                f"to delete the file, which no worker tool can do.",
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
            f"in this problem: {detail}. Pick a different decomposition — "
            f"or, if you believe the statement is true after all, decline "
            f"and say so: a disproved mark records a CLAIMED "
            f"counterexample, and the Strategist can revive the original "
            f"goal rather than mint a twin.",
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

    # Dead-twin guard (agent_feedback 2026-07-09/10, ~35 entries): a
    # sub-goal statement-equivalent to a DEAD goal is a blind repeat of an
    # exhausted attempt — b6 burned 3-4 full Backward turns re-walking a
    # same-day counterexampled decline. Decline WITH the twin's prior
    # failure forensics so the retry / next Strategist sees WHY it died.
    # World-changed release: if any goal PROVED after the twin died, the
    # toolkit grew — the retry is legitimate (the designed revival path),
    # so the match is neutralized and the sub-goal mints as novel.
    dead_pairs = [
        (idx, slug, m.goal_id)
        for idx, ((slug, _), m) in enumerate(zip(sub_meta, canonical_for))
        if m is not None and m.kind == "dead"
    ]
    blocking_dead: list[str] = []
    for idx, slug, dgid in dead_pairs:
        why = _dead_twin_block_reason(conn, goal["problem"], dgid)
        if why is None:
            canonical_for[idx] = None  # world changed — retry allowed
            continue
        blocking_dead.append(f"`{slug}` {why}")
    if blocking_dead:
        return _abort(
            "same_as_dead_unchanged",
            "sub-goal(s) restate a DEAD twin and nothing has been proved "
            "in this problem since it died — a byte-identical retry in an "
            "unchanged world repeats the same failure:\n  "
            + "\n  ".join(blocking_dead)
            + "\nEither change the statement (weaker/refactored), or "
            "first land the missing tool the prior failure names.",
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
        # Sub-goal stub normalization (unified assemble, task #5 Step B).
        # carry_opens: the strategy patch's own file-scope opens — validate's
        # compilation unit ALWAYS elaborated the stubs under these, but the
        # committed files never carried them, so a statement using the
        # patch's `open scoped …` notation was validate-green / lake-red
        # (the backward_subgoal_needs_own_open_scoped trap class). conn +
        # declared_slugs: proved-sibling imports for stub STATEMENTS that
        # reference a harvested def / proved sibling (the framework only
        # auto-imported those into the strategy file, another commit-only
        # asymmetry — backward_subgoal_stmt_needs_harvested_def_imports).
        _batch_slugs = {slug for slug, _ in sub_meta}
        _patch_opens = assemble.harvest_open_lines(main_patch_text)

        # Intra-batch import edges (task #84): stub A referencing batch
        # sibling B gets `import …proofs.L_B` injected MECHANICALLY —
        # the reference is a fact of the batch the framework can see,
        # not something the agent must remember (the silent
        # validate-green/lake-red class: validate inlines the batch
        # into one unit where B always resolves; the split module
        # didn't — sphere `sphere_equator_equiv_forward_cont`,
        # MV `mv_delta`, each a whole-spawn burn). Cycles admit no
        # import order — reject pre-placement (the submission mirror
        # predicts them in-session via `split_visibility_issues`).
        _stub_texts = {s: p.read_text(encoding="utf-8")
                       for s, p in sub_meta}
        _batch_edges = assemble.batch_reference_edges(_stub_texts)
        _batch_cycles = assemble.batch_reference_cycles(_batch_edges)
        if _batch_cycles:
            chain = " → ".join(_batch_cycles[0])
            return _abort(
                "batch_reference_cycle",
                f"batch sub-goals reference each other in a cycle "
                f"({chain}) — Lean modules cannot mutually import, so no "
                f"placement order exists. Merge the statements into one "
                f"sub-goal, or restate one side so it does not mention "
                f"the other.",
                leading,
            )

        def _novel_content(raw: str, slug: str) -> str:
            """Sub-goal placed for normal dispatch — elaborates standalone
            under the SAME imports/opens validate's unit gave it, plus its
            mechanically-derived intra-batch import edges."""
            extra = tuple(
                f"import Problems.{goal['problem']}.proofs.L_{b}"
                for b in _batch_edges.get(slug, ()))
            return assemble.assemble_for_commit(
                raw, problem=goal["problem"], workspace=workspace,
                conn=conn, declared_slugs=_batch_slugs,
                carry_opens=_patch_opens, extra_imports=extra).text

        for idx, ((slug, src), (_, dest), match) in enumerate(zip(
            sub_meta, sub_dests, canonical_for,
        )):
            raw = src.read_text(encoding="utf-8")
            if match is not None and not dedupe._SORRY_BODY_RE.search(raw):
                # Defense-in-depth (mv_delta 2026-07-03): only a SORRY-BEARING
                # sub-goal is aliasable. `build_alias_content` rewrites
                # `:= by sorry` → the delegation, and the build-verify below
                # then tests THAT delegation. A complete sub-goal has nothing
                # to delegate → the build-verify would validate its own proof,
                # rubber-stamping a spurious probe match. Decline → keep its
                # own content as a novel sub-goal. Mirrors the build-verify-
                # fail fallback + verify.promote_to_alias's guard (verify.py:306).
                print(f"[dedupe] {slug}: sub-goal is already a complete proof "
                      f"(no `:= by sorry`) — not aliasing; keeping as novel",
                      flush=True)
                match = None
                canonical_for[idx] = None
            if match is not None:
                # Build the alias body on top of import/opens-injected
                # content so the file elaborates standalone (agent
                # `new_<slug>.lean` files often omit `import Mathlib`).
                if match.kind == "library_alias":
                    # A — cross-problem reuse: canonical is a proved
                    # `Library/` decl (no in-DB goal). Delegate via the
                    # fully-qualified name (its namespace isn't open here).
                    alias_content = dedupe.build_alias_content(
                        original_content=_novel_content(raw, slug),
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
                        original_content=_novel_content(raw, slug),
                        canonical_module=canonical_module,
                        canonical_slug=canonical["slug"],
                    )
                    canonical_label = f"goal {canonical_id} ({canonical['slug']})"
                _place_unowned(conn, workspace, dest, alias_content)
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
                av = _verify_owned(dest, write_olean=True)
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
                    _place_unowned(conn, workspace, dest, _novel_content(raw, slug))
            else:
                _place_unowned(conn, workspace, dest, _novel_content(raw, slug))
            placed.append(dest)
        _place_unowned(
            conn, workspace, scratch_dest,
            patches[0].read_text(encoding="utf-8"))
        placed.append(scratch_dest)

        # #2 — rewrite reuse sub-goals into citations of their twin (swap
        # the slug token for the twin's theorem name + inject its import).
        # The citation gate below then auto-links / revives the twin and
        # the strategy waits for it.
        if reuse_rewrites:
            _place_unowned(
                conn, workspace, scratch_dest,
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
        # Unified commit normalization for the strategy scratch (task #5
        # Step B): Defs opens (formerly injected right at placement — every
        # transform is idempotent and content-independent, so running once
        # here, AFTER the reuse rewrites + sub-goal imports, is equivalent)
        # + proved-sibling imports, via the same assemble_for_commit every
        # other commit path runs. Rewrite the scratch before the cite-gate
        # + build see it.
        _asm = assemble.assemble_for_commit(
            scratch_dest.read_text(encoding="utf-8"),
            problem=goal["problem"], workspace=workspace,
            conn=conn, declared_slugs=declared_slugs)
        scratch_text = _asm.text
        if _asm.injected_sibling_imports:
            print(f"[cite] auto-imported "
                  f"{len(_asm.injected_sibling_imports)} proved sibling(s): "
                  f"{', '.join(_asm.injected_sibling_imports)}", flush=True)
        if scratch_text != scratch_dest.read_text(encoding="utf-8"):
            _place_unowned(conn, workspace, scratch_dest, scratch_text)
        auto_link_ids, revive_ids, cite_err = _resolve_cite_dependencies(
            conn, problem=goal["problem"], patch_text=scratch_text,
            declared_slugs=declared_slugs, allow_auto_link=True,
            workspace=workspace,
        )
        if cite_err:
            _discard_placed()
            return _abort("cite_unproved_sibling", cite_err, leading)

        # Cited-dependency guards (structural cycle + semantic no-progress)
        # — shared with the stub-less commit path so both shapes of
        # "this patch waits on a cited sibling" are held to one standard.
        guard = _cited_dependency_guards(
            conn, workspace, problem=goal["problem"], goal_id=goal_id,
            auto_link_ids=set(auto_link_ids))
        if guard is not None:
            _discard_placed()
            return _abort(guard[0], guard[1], leading)

        # P3 duplicate-strategy guard (agent_feedback 2026-07-11, the b6
        # strategy pile: ~30 byte-identical reductions s22785–s22831): a
        # decomposition with NO novel sub-goal whose linked-goal set
        # equals an existing proposed/stalled strategy's subgoal set on
        # this goal adds nothing — the existing strategy is already
        # waiting on exactly the same gates. Decline with the twin
        # strategy named so the Strategist stops re-asserting it.
        # Novel stubs exempt: new content = a genuinely new strategy.
        if not sub_meta and auto_link_ids:
            dup_sid = _existing_duplicate_strategy(
                conn, goal_id, set(auto_link_ids))
            if dup_sid is not None:
                _discard_placed()
                return _abort(
                    "duplicate_strategy",
                    f"this decomposition declares no novel sub-goal and "
                    f"links exactly the same goal set "
                    f"{sorted(auto_link_ids)} as existing strategy "
                    f"s{dup_sid} on this goal — it is a byte-identical "
                    f"re-assertion; s{dup_sid} is already waiting on "
                    f"those gates. Nothing new will happen that is not "
                    f"already pending.",
                    leading,
                )

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
        # Sub-goal stubs additionally ask for decl_info — the statement
        # mint below reads each stub's kernel-true ppSignature off the
        # elaboration this loop already pays for (decl-#1: the text
        # extractor's conclusion is origin- and author-format-dependent;
        # the pp conclusion is canonical, and exists even for an
        # inferred-type def).
        sub_dest_set = {dest for _, dest in sub_dests}
        decl_info_by_path: dict = {}
        for path in placed:
            want_info = path in sub_dest_set
            v = _verify_owned(path, write_olean=True, decl_info=want_info)
            if want_info and isinstance(v, dict) and v.get("decl_info"):
                decl_info_by_path[path] = v["decl_info"]
            if "error" in v:
                # THE FOURTH ARM. These used to `raise RuntimeError`,
                # and the outer handler stamps every non-OSError escape
                # `lake_build_error` — so this path re-grew the exact
                # disease the 08-12 fix cured in the leaf-bypass arm
                # (an unreachable gateway burned a goal attempt as
                # "your Lean failed"; #213, live rows on 08-16/17). The
                # guard that should have caught it only greps for the
                # call appearing SOMEWHERE in this file.
                _discard_placed()
                from ..state.failures import verify_error_reason
                return _abort(
                    verify_error_reason(v) or "lake_build_error",
                    diagnostics.annotate_failure_detail(
                        f"verify infra error on {path.name}: {v['error']}"),
                    leading)
            if not v.get("ok"):
                err_lines = "\n".join(
                    f"{path.name}:{d.get('line','?')}:{d.get('col','?')}  "
                    f"{d.get('severity','?')}: {d.get('message','')}"
                    for d in (v.get("diagnostics") or [])
                    if d.get("severity") == "error"
                )
                _discard_placed()
                if not err_lines:
                    # ok=false with ZERO error diagnostics is a
                    # worker-side failure shape (crashed worker, empty
                    # reply) — there is no Lean verdict here and nothing
                    # for the agent to fix (g7894's "lake build failed:
                    # no error" row, 2026-08-17).
                    return _abort(
                        "framework_verify_error",
                        f"verify returned ok=false with no error "
                        f"diagnostics on {path.name} — a worker-side "
                        f"failure, not a Lean verdict",
                        leading)
                return _abort(
                    "lake_build_error",
                    diagnostics.annotate_failure_detail(
                        f"lake build failed: {err_lines}"),
                    leading)

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
            # Oracle-first statement mint (decl-#1): the pp conclusion off
            # the verify loop's decl_info piggyback; text extraction stays
            # as the cold fallback (stub verifiers / old gateway).
            from ..lsp.decl_oracle import statement_from_decl_info
            stmt = (statement_from_decl_info(decl_info_by_path.get(dest),
                                             slug)
                    or _extract_statement_from_lean(dest))
            rel = dest.relative_to(workspace).as_posix()
            raw = dest.read_text(encoding="utf-8")
            # entry_kind routing retired (v33). Legacy-shaped stubs may
            # still carry the `-- entry_kind:` comment — strip it so it
            # doesn't linger in proofs/ or propagate into the Library.
            cleaned = _strip_entry_kind(raw)
            if cleaned != raw:
                _place_unowned(conn, workspace, dest, cleaned)
            new_gid = db.insert_goal(
                conn, problem=goal["problem"], slug=slug,
                lean_path=rel, statement=stmt, origin="backward",
                depth=goal["depth"] + 1,
            )
            if match is not None:
                # Past the same_as_disproved / no_progress early-returns →
                # kind is "alias" (in-problem) or "library_alias" (A).
                transitions.apply_goal_transition(
                    conn, new_gid, "proved", event="backward_alias_proved",
                    receipt=transitions.ProvedReceipt(
                        "alias_induction",
                        f"dedupe {match.kind} → g{match.goal_id} "
                        f"(build-verified)"))
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
                # effective_axioms: an unset whitelist used to hit
                # axiom_probe's fail-closed branch (promotion refused
                # outright); the goal then re-proved through the normal
                # path against the SAME default whitelist. Deriving it
                # here makes the sub-goal promote behave like every other
                # gate (finding-3 unification; net verdicts unchanged).
                ok, msg = _try_promote_sorry_free(
                    dest=dest, problem=goal["problem"], slug=slug,
                    workspace=workspace,
                    axioms_whitelist=intent_mod.effective_axioms(
                        intent, problem=goal["problem"]),
                    attempts_dir=attempts_dir,
                )
                if ok:
                    transitions.apply_goal_transition(
                        conn, new_gid, "proved",
                        event="backward_sorryfree_proved",
                        receipt=transitions.ProvedReceipt(
                            "axiom_gate", msg))
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
        # AN OSError HERE IS OURS, NOT THE AGENT'S. This handler covers
        # ~450 lines of placement / verify / insert, and it labelled
        # every escape `lake_build_error` — origin `agent`,
        # attempt-burning, agent-visible. Measured 2026-08-15: a spawn
        # the framework believed it had killed was still alive and
        # called `withdraw_stub`, deleting a stub file between this
        # path's glob and its read; the `FileNotFoundError` came back to
        # the agent as "your Lean failed to build". `worker_exception`
        # is the registry's framework-origin, non-agent-visible entry
        # for exactly this (`state/failures.py:203`); `lake_build_error`
        # keeps only the verdicts that carry Lean diagnostics.
        return _abort(
            "worker_exception" if isinstance(exc, OSError)
            else "lake_build_error",
            diagnostics.annotate_failure_detail(str(exc)),
            leading,
        )
