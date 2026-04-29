"""Statement-level dedup for goals proposed by Backward.

When OR parallelism produces multiple Backwards on the same parent goal,
their independently-generated sub-goals often overlap in content. This
module identifies a candidate sub-goal as equivalent to an existing goal
in the same problem; run_backward then writes a thin alias lean file
(`theorem <new_slug> := <canonical_slug>`) instead of a fresh sorry stub
and links the strategy to the existing goal via `strategy_subgoals`.

Effect: when canonical proves, every alias automatically inherits the
proof — no duplicate compute on overlapping sub-goals across OR sibling
strategies.

Comparison is currently whitespace-normalized text equality (catches the
high-confidence cases of identical agent output). The single
`_statements_equivalent` predicate is the swap point for future
strengthening (α-rename / Lean.Meta.isDefEq via subprocess).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path


_WS_RE = re.compile(r"\s+")


def _normalize_statement(s: str) -> str:
    """Collapse all whitespace to single spaces; strip ends. Future
    upgrade target: α-equivalence via binder renaming."""
    return _WS_RE.sub(" ", s.strip())


def _statements_equivalent(a: str, b: str) -> bool:
    """Single predicate that decides 'these two Lean statements are the
    same up to dedupe equivalence'. Swap-point for future modes."""
    return _normalize_statement(a) == _normalize_statement(b)


def find_canonical(conn: sqlite3.Connection, problem: str,
                   statement: str) -> int | None:
    """Find an existing goal in `problem` whose statement is equivalent
    to `statement`. Returns the canonical goal_id, or None.

    Selection order (deterministic):
      1. status='proved' (alias inherits real proof, never breaks)
      2. reachable open/attempting (alias inherits if/when canonical proves)
      3. tie-break by earliest id

    Skips status in ('superseded','dead','shelved') and any goal whose
    lineage chain back to root passes through a non-alive strategy
    (orphan) — aliasing to those would produce stale references.
    """
    if not statement.strip():
        return None

    rows = conn.execute(
        "SELECT g.id, g.statement, g.status FROM goals g "
        "WHERE g.problem = ? "
        "  AND g.status IN ('proved','open','attempting') "
        "  AND (g.origin = 'root' OR g.id IN ("
        "    WITH RECURSIVE alive(id) AS ("
        "      SELECT id FROM goals WHERE problem = ? AND origin = 'root'"
        "      UNION"
        "      SELECT g2.id FROM goals g2"
        "      JOIN strategy_subgoals ss ON ss.subgoal_id = g2.id"
        "      JOIN strategies s ON s.id = ss.strategy_id"
        "      JOIN alive a ON a.id = s.goal_id"
        "      WHERE s.status IN ('proposed','succeeded')"
        "    ) SELECT id FROM alive"
        "  )) "
        "ORDER BY (g.status = 'proved') DESC, g.id ASC",
        (problem, problem),
    ).fetchall()

    for r in rows:
        if _statements_equivalent(r["statement"], statement):
            return int(r["id"])
    return None


def build_alias_content(*, problem: str, new_slug: str, statement: str,
                        canonical_slug: str, canonical_module: str,
                        defs_imported: bool) -> str:
    """Build the alias lean file content. Lake-builds against any
    canonical state (sorry stub, partial proof, or fully proved); the
    alias inherits canonical's proof transitively."""
    imports = ["import Mathlib"]
    if defs_imported:
        imports.append(f"import Problems.{problem}.Defs")
    imports.append(f"import {canonical_module}")
    return (
        "\n".join(imports) + "\n\n"
        f"namespace Problems.{problem}\n\n"
        f"theorem {new_slug} : {statement} := {canonical_slug}\n\n"
        f"end Problems.{problem}\n"
    )
