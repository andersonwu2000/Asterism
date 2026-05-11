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

from . import db


def _lean_path_to_module(workspace: Path, lean_path: Path) -> str:
    """workspace-relative path → Lean module name (mirrors pipeline.py)."""
    rel = lean_path.relative_to(workspace).with_suffix("")
    return ".".join(rel.parts)


_STRATEGY_IMPORT_PATTERN = "proofs._strategy_s"


def _canonical_alias_content(*, problem: str, goal_slug: str,
                             sid_token: str, scratch_module: str,
                             current: str) -> str:
    """Canonical end-of-run content for a proved goal's lean_path.

    Same shape Verify Step 2's `_promote_to_alias` writes (def-alias
    so Lean copies type from the strategy theorem; pre-F52 used
    `theorem <slug> : <statement> := s<sid>` which lost binders).
    Difference from Verify-time promotion: reconcile DROPS any
    `_strategy_s*` imports other than the winning strategy's, so
    drift from sibling Verify races is repaired exclusively.
    """
    keep_imports: list[str] = []
    seen: set[str] = set()
    for ln in current.splitlines():
        s = ln.strip()
        if not s.startswith("import"):
            continue
        if _STRATEGY_IMPORT_PATTERN in s:
            continue  # drop ALL prior strategy imports (winner re-added below)
        if s in seen:
            continue
        seen.add(s)
        keep_imports.append(ln)
    winner = f"import {scratch_module}"
    if winner not in seen:
        keep_imports.append(winner)
    return (
        "\n".join(keep_imports) + "\n\n"
        f"namespace Problems.{problem}\n\n"
        f"def {goal_slug} := @Problems.{problem}.{sid_token}\n\n"
        f"end Problems.{problem}\n"
    )


def reconcile_proved_goals(conn: sqlite3.Connection, workspace: Path,
                           problem: str) -> list[Path]:
    """Repair file/DB drift after OR Verify races.

    For each proved goal that has a 'succeeded' strategy, rewrite its
    lean_path to alias EXCLUSIVELY from that strategy's scratch — no
    stale imports from sibling strategies that finished concurrently.

    Form matches Verify Step 2's `_promote_to_alias` (P0-#2: prior
    version emitted `theorem <slug> : <statement> := s<sid>`, which
    serializes only the goal's conclusion — binders from the original
    stub were stripped, breaking elaboration on any non-trivially-
    bound goal; this regenerated form would silently undo F52's fix
    every end-of-run reconcile). Idempotent — already-canonical
    files are left alone.

    Returns the list of repaired paths.
    """
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
        parent_abs = workspace / r["lean_path"]
        scratch_module = _lean_path_to_module(workspace, scratch_abs)
        sid_token = f"s{int(r['sid'])}"
        try:
            current = parent_abs.read_text(encoding="utf-8") if parent_abs.exists() else ""
        except OSError:
            continue
        expected = _canonical_alias_content(
            problem=problem, goal_slug=r["slug"],
            sid_token=sid_token, scratch_module=scratch_module,
            current=current,
        )
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
            "SELECT lean_path, alias_target_id FROM goals WHERE id = ?",
            (goal_id,),
        ).fetchone()
        if goal is None:
            return
        keep.add(goal["lean_path"])

        # F42 — alias goals' lean files import their canonical's file.
        # Walk into the canonical so its lean_path stays in `keep` even
        # when the canonical is an orphan from a dead/superseded
        # strategy. Visited-set prevents loops; chain stays flat in
        # practice (insertion never aliases to an alias — see dedupe
        # _eligible_orphan_subgoals filter).
        if goal["alias_target_id"] is not None:
            walk(int(goal["alias_target_id"]))

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

    proofs_dir = db.problem_dir(workspace, problem) / "proofs"
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
