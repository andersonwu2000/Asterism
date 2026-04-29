"""End-of-run reconciliation + GC for OR parallelism artifacts.

OR parallelism produces two cleanup needs:

(1) **drift repair** (`reconcile_proved_goals`). When two sibling Verify
    workers race to rewrite a parent goal's lean_path, last-write-wins
    on the filesystem; the cascade-determined winner may not match the
    file-state winner. This function re-derives each proved goal's
    lean_path canonically from the DB winning strategy's scratch.

(2) **orphan GC** (`prune_problem`). Backwards that died and OR siblings
    that lost the race leave lean files in `proofs/`. Walking the DB
    winning chain identifies the live set; everything else is deletable.

Both run at dispatcher's all-roots-proved exit (self-healing invariant)
and via `asterism prune` CLI for partial state.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def _lean_path_to_module(workspace: Path, lean_path: Path) -> str:
    """workspace-relative path → Lean module name (mirrors pipeline.py)."""
    rel = lean_path.relative_to(workspace).with_suffix("")
    return ".".join(rel.parts)


def _canonical_parent_content(*, problem: str, goal_slug: str,
                              goal_statement: str, sid: int,
                              defs_exists: bool, scratch_module: str) -> str:
    """Build the deterministic content for a proved goal's lean_path."""
    imports = ["import Mathlib"]
    if defs_exists:
        imports.append(f"import Problems.{problem}.Defs")
    imports.append(f"import {scratch_module}")
    return (
        "\n".join(imports) + "\n\n"
        f"namespace Problems.{problem}\n\n"
        f"theorem {goal_slug} : {goal_statement} := "
        f"s{sid}_{goal_slug}\n\n"
        f"end Problems.{problem}\n"
    )


def reconcile_proved_goals(conn: sqlite3.Connection, workspace: Path,
                           problem: str) -> list[Path]:
    """Repair file/DB drift after OR Verify races.

    For each proved goal that has a 'succeeded' strategy, rewrite its
    lean_path to alias EXCLUSIVELY from that strategy's scratch — no
    stale imports from sibling strategies that finished concurrently.

    Idempotent: a file already matching the canonical form is left alone.
    Returns the list of repaired paths.
    """
    defs_exists = (workspace / "Problems" / problem / "Defs.lean").exists()
    repaired: list[Path] = []

    rows = conn.execute(
        "SELECT g.id AS gid, g.slug, g.statement, g.lean_path,"
        "       s.id AS sid, s.scratch_path "
        "FROM goals g "
        "JOIN strategies s ON s.goal_id = g.id "
        "WHERE g.problem = ? AND g.status = 'proved'"
        "  AND s.status = 'succeeded'",
        (problem,),
    ).fetchall()

    for r in rows:
        if not r["scratch_path"]:
            continue
        scratch_abs = workspace / r["scratch_path"]
        if not scratch_abs.exists():
            continue
        scratch_module = _lean_path_to_module(workspace, scratch_abs)
        expected = _canonical_parent_content(
            problem=problem, goal_slug=r["slug"],
            goal_statement=r["statement"], sid=int(r["sid"]),
            defs_exists=defs_exists, scratch_module=scratch_module,
        )
        parent_abs = workspace / r["lean_path"]
        try:
            current = parent_abs.read_text(encoding="utf-8")
        except OSError:
            continue
        if current == expected:
            continue
        parent_abs.write_text(expected, encoding="utf-8")
        repaired.append(parent_abs)

    return repaired


def winning_chain(conn: sqlite3.Connection, problem: str) -> set[str]:
    """Set of repo-relative lean paths reachable from `problem`'s proved
    roots through 'succeeded' strategies. Includes both the goal lean files
    and the strategy scratch files of the winning chain."""
    keep: set[str] = set()
    visited: set[int] = set()

    def walk(goal_id: int) -> None:
        if goal_id in visited:
            return
        visited.add(goal_id)
        goal = conn.execute(
            "SELECT lean_path FROM goals WHERE id = ?", (goal_id,),
        ).fetchone()
        if goal is None:
            return
        keep.add(goal["lean_path"])

        # A proved goal is closed either by Builder (no succeeded strategy)
        # or by a single 'succeeded' Strategy. Recurse only into the latter.
        s = conn.execute(
            "SELECT id, scratch_path FROM strategies"
            " WHERE goal_id = ? AND status = 'succeeded' LIMIT 1",
            (goal_id,),
        ).fetchone()
        if s is None:
            return
        if s["scratch_path"]:
            keep.add(s["scratch_path"])
        for sub in conn.execute(
            "SELECT subgoal_id FROM strategy_subgoals WHERE strategy_id = ?",
            (s["id"],),
        ):
            walk(int(sub["subgoal_id"]))

    for row in conn.execute(
        "SELECT id FROM goals"
        " WHERE problem = ? AND origin = 'root' AND status = 'proved'",
        (problem,),
    ):
        walk(int(row["id"]))

    return keep


def prune_problem(conn: sqlite3.Connection, workspace: Path,
                  problem: str, *, dry_run: bool = False) -> list[Path]:
    """Delete every `.lean` in `Problems/<problem>/proofs/` that is not
    in the winning chain. Returns the list of removed paths.

    No-op (returns []) when the problem's root goal is not yet proved —
    we don't know what's safe to delete during a running proof attempt.

    Idempotent: a second call after the first has cleaned everything
    finds nothing to remove.
    """
    has_proved_root = conn.execute(
        "SELECT 1 FROM goals"
        " WHERE problem = ? AND origin = 'root' AND status = 'proved' LIMIT 1",
        (problem,),
    ).fetchone()
    if has_proved_root is None:
        return []

    keep_rel = winning_chain(conn, problem)
    keep_abs = {(workspace / rel).resolve() for rel in keep_rel}

    proofs_dir = workspace / "Problems" / problem / "proofs"
    if not proofs_dir.exists():
        return []

    removed: list[Path] = []
    for f in proofs_dir.glob("*.lean"):
        if f.resolve() in keep_abs:
            continue
        if not dry_run:
            try:
                f.unlink()
            except OSError:
                continue
        removed.append(f)
    return removed
