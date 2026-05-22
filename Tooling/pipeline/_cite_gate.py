"""Shared citation-gate logic for Backward (decomp + leaf-bypass) and
Builder pipelines.

Extracted from `backward.py` 2026-05-22 — Builder had no citation gate,
so an agent that wrote `import Problems.<p>.proofs.L_<shelved_slug>`
into Builder's `patch.lean` would not be rejected at commit time; the
shelved wrapper's underlying strategy still elaborates (sorry surfaces
as warning, not error), the build "passes", and the sorry propagates
up through goal_lean → cascade until `root_integrity_gate` finally
catches it. By that time many spawn cycles are burnt.

Gate is per-patch: scan for `import Problems.<problem>.proofs.L_<slug>`
lines and classify each cited slug by goal status:
- `proved`: legitimate, pass through.
- `open` / `attempting` / `pending_strategist_review`: if the caller
  supports auto-linking (decomposition path), collect the goal_id so
  the caller can attach a `strategy_subgoals` row and have the new
  strategy wait until the cited goal proves; otherwise (leaf-bypass /
  Builder) reject.
- `shelved` / `disproved` / `dead`: always reject — terminal-failed
  goals will not be revived in this strategy's lifetime; agent must
  pick a different angle.
- Unknown slug / cross-problem import: pass through (lake's "unknown
  identifier" path will catch genuine typos).
"""
from __future__ import annotations

import re
import sqlite3


# `import Problems.<problem>.proofs.L_<slug>` line pattern.
# Captures (problem, slug). Multiline so it matches per-line in patch_text.
_PROBLEM_IMPORT_RE = re.compile(
    r"^\s*import\s+Problems\.([A-Za-z_][\w.]*)\.proofs\.L_([a-z][a-z0-9_]*)\s*$",
    re.MULTILINE,
)


def _resolve_cite_dependencies(
    conn: sqlite3.Connection, *, problem: str, patch_text: str,
    declared_slugs: set[str], allow_auto_link: bool,
) -> tuple[set[int], str | None]:
    """Scan `patch_text` for `import Problems.<problem>.proofs.L_<slug>`
    lines and classify each cited slug:

      * declared sub-goal (in this commit's `new_<slug>.lean` files) → skip
      * status='proved' goal → skip (legitimate citation)
      * status ∈ ('open', 'attempting', 'pending_strategist_review'):
        - if `allow_auto_link`: collect goal_id for caller to insert as
          a sibling sub-goal via `strategy_subgoals` (the safe parallel
          pattern — strategy waits in 'proposed' until cited goal proves
          via `strategies_ready_for_verify`'s all-subgoals-proved check)
        - else: reject (caller is a leaf-bypass / Builder that runs
          axiom probe at submit, can't tolerate transitive sorry from
          cited stub)
      * status ∈ ('shelved', 'disproved', 'dead') → reject (cited goal
        can't be revived in this strategy's lifetime; agent must pick
        a different angle)
      * unknown slug / cross-problem import → skip (lake's
        "unknown identifier" catches genuine typos)

    Returns (auto_link_goal_ids, err). Caller commits the strategy
    with the declared subgoals plus auto-linked goals as
    additional `strategy_subgoals` rows. On err non-None the strategy
    must abort (subgoals would be from a doomed dependency).
    """
    auto_link: set[int] = set()
    bad: list[tuple[str, str]] = []
    seen: set[str] = set()
    for m in _PROBLEM_IMPORT_RE.finditer(patch_text):
        if m.group(1) != problem:
            continue
        slug = m.group(2)
        if slug in seen:
            continue
        seen.add(slug)
        if slug in declared_slugs:
            continue
        row = conn.execute(
            "SELECT id, status FROM goals WHERE problem = ? AND slug = ?"
            " AND alias_target_id IS NULL",
            (problem, slug),
        ).fetchone()
        if row is None:
            # No matching goal — lake's "unknown identifier" path will
            # catch genuinely invalid imports. Don't double-reject here.
            continue
        status = str(row["status"])
        if status == "proved":
            continue
        if status in ("open", "attempting",
                       "pending_strategist_review"):
            if allow_auto_link:
                auto_link.add(int(row["id"]))
            else:
                bad.append((slug, status))
            continue
        # ('shelved', 'disproved', 'dead') — terminal-failed, can't
        # recover even with parallel wait.
        bad.append((slug, status))
    if not bad:
        return auto_link, None
    lines = [f"  - `{slug}` (status={status})" for slug, status in bad]
    if allow_auto_link:
        # Decomp path's only reject reason is terminal-failed cites
        # — guide the agent toward a different angle.
        hint = (
            "\n\nThese goals are terminal-failed in this strategy's "
            "context — they will not prove. Rewrite the proof to avoid "
            "the citations, or pick a different decomposition angle."
        )
    else:
        # Leaf-bypass / Builder path: any non-proved cite is rejected
        # (immediate axiom probe can't tolerate transitive sorry). The
        # auto-link mechanism is only available via Backward decomp.
        hint = (
            "\n\nFix by declaring each as a sub-goal stub "
            "(`new_<slug>.lean := by sorry`) — the decomposition path "
            "auto-links open siblings as `strategy_subgoals` so the "
            "strategy waits for them to prove. Leaf-bypass strategies "
            "and Builder (no decomposition) can only cite already-"
            "proved siblings."
        )
    return auto_link, (
        "Patch imports sibling goals that cannot be cited:\n"
        + "\n".join(lines) + hint
    )
