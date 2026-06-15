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
- `shelved` / `dead`: SOFT/context terminals. The `goals.status`
  contract (db.py) makes these the statuses dedupe does NOT block —
  shelved is "reopenable", dead is "same statement may be valid under a
  different parent strategy". Citability mirrors dedupe-blocking, so on
  the decomposition path these are REVIVED: reopened to `open` and
  auto-linked, regaining a live path through the citing strategy's
  `strategy_subgoals`. (Pre-2026-06-13 they were rejected alongside
  `disproved`, which contradicted the contract and left cascade-shelved
  leaves uncitable forever — agent_feedback T8.) Leaf-bypass / Builder
  still reject (can't tolerate transitive sorry).
- `disproved`: HARD terminal — a counterexample was found, dedupe
  BLOCKS it, so does citation. The one status that is never citable.
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
) -> tuple[set[int], set[int], str | None]:
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
      * status='shelved' — soft terminal that dedupe does NOT block:
        - if `allow_auto_link`: collect goal_id in BOTH the auto-link set
          (links as a `strategy_subgoals` row) AND the revive set (caller
          reopens it to 'open' — the citing strategy gives it a fresh live
          path back to root, so it re-dispatches). Fixes cascade-shelved
          leaves being uncitable forever (agent_feedback T8).
        - else: reject (leaf-bypass / Builder can't tolerate transitive
          sorry; revival is a decomposition-path capability).
      * status ∈ ('dead', 'disproved') → always reject (never revived):
        - 'dead' = wrong AS STATED in its parent's decomposition
          (parent_needs_fix); the db.py `goals.status` contract makes it
          never-Reopen, so citing it would re-attempt a known-wrong
          statement. The same statement may be valid in a fresh context —
          re-declare it as your own `new_<slug>.lean` sub-goal stub (a
          corrected re-statement under your strategy) instead of citing
          the dead goal.
        - 'disproved' = counterexample found; the statement is false.
      * unknown slug / cross-problem import → skip (lake's
        "unknown identifier" catches genuine typos)

    Returns (auto_link_goal_ids, revive_goal_ids, err). `revive` ⊆
    `auto_link`. Caller commits the strategy with the declared subgoals
    plus `auto_link` goals as additional `strategy_subgoals` rows, and
    reopens every `revive` goal (currently shelved/dead) to 'open' first.
    On err non-None the strategy must abort (subgoals would be from a
    doomed dependency).
    """
    auto_link: set[int] = set()
    revive: set[int] = set()
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
        if status == "shelved":
            # Soft terminal — revivable. dedupe doesn't block it, so
            # neither does citation: reopen + auto-link on the decomp
            # path; reject on leaf-bypass/Builder (transitive sorry).
            if allow_auto_link:
                auto_link.add(int(row["id"]))
                revive.add(int(row["id"]))
            else:
                bad.append((slug, status))
            continue
        # 'dead' / 'disproved' — hard terminals, never revived by citation.
        #  - 'dead' = the statement is wrong AS STATED in its parent's
        #    decomposition (parent_needs_fix); reviving re-attempts a
        #    known-wrong statement (db.py goals.status contract: dead is
        #    never-Reopen). A corrected re-statement under a fresh context
        #    is fine — re-declare it as a `new_<slug>.lean` stub instead.
        #  - 'disproved' = counterexample found; the statement is false.
        bad.append((slug, status))
    if not bad:
        return auto_link, revive, None
    lines = [f"  - `{slug}` (status={status})" for slug, status in bad]
    if allow_auto_link:
        # On the decomp path `bad` holds disproved (false) and dead
        # (wrong-as-stated) cites; shelved are revived above.
        hint = (
            "\n\nThese goals cannot be cited: DISPROVED = a counterexample "
            "was found (the statement is false); DEAD = wrong as stated in "
            "its parent's decomposition, so citing re-attempts a known-wrong "
            "statement. Re-declare a dead goal's statement as your own "
            "`new_<slug>.lean` sub-goal stub (a corrected re-statement under "
            "your strategy), or pick a different decomposition angle."
        )
    else:
        # Leaf-bypass / Builder path: any non-proved cite is rejected
        # (immediate axiom probe can't tolerate transitive sorry). The
        # auto-link / revive mechanism is only available via Backward
        # decomp.
        hint = (
            "\n\nFix by declaring each as a sub-goal stub "
            "(`new_<slug>.lean := by sorry`), or restructure as a "
            "Backward decomposition — the decomp path auto-links open "
            "siblings and revives shelved/dead ones as `strategy_"
            "subgoals` so the strategy waits for them to prove. Leaf-"
            "bypass and Builder (no decomposition) can only cite "
            "already-proved siblings."
        )
    return auto_link, revive, (
        "Patch imports sibling goals that cannot be cited:\n"
        + "\n".join(lines) + hint
    )
