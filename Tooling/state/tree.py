"""Per-Problem AND/OR proof tree renderer.

`Problems/<p>/TREE.md` is the canonical human-facing view of a Problem's
proof progress. Auto-updated by the dispatcher on every cascade so the
file always reflects the latest state — readers can leave it open in
an editor / file watcher.

Tree shape mirrors the AND/OR graph:

    main  (attempting, attempts=1)
    ├── via s15  (dead — sub-goal shelved)
    │   ├── s15_sub_1  (shelved, attempts=8)
    │   ├── s15_sub_2  (attempting)
    │   │   └── via s18  (proposed)
    │   │       ├── s18_sub_1  (proved)
    │   │       └── s18_sub_2  (open, attempts=5)
    │   └── ...
    └── via s36  (proposed — OR retry)
        └── ...

`via sNN` lines are Strategy nodes (the AND layer); their children
are sub-Goals. A Goal can have multiple Strategies (OR alternatives),
all rendered as siblings under the Goal.

Identifiers are slug-only (the DB id is internal, not meaningful to
readers). `s<NN>_sub_<k>` already encodes the parent strategy ancestry,
so cross-references are visually self-evident.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from . import db


_DEAD_CAUSE_SUBGOAL_SHELVED = "sub-goal shelved"
_DEAD_CAUSE_VERIFY = "verify failed"


def _strategy_dead_cause(conn: sqlite3.Connection, strategy_id: int
                         ) -> str | None:
    """Best-effort short note for why a strategy died: scan its
    sub-goals for a shelved one (cascade kill via _propagate_shelve);
    fall back to checking dead_attempts for a Verify failure on this
    strategy. Returns None when neither evidence is present (caller
    elides the cause clause to avoid noisy 'dead — dead' rendering)."""
    shelved = conn.execute(
        "SELECT 1 FROM strategy_subgoals ss "
        "JOIN goals g ON g.id = ss.subgoal_id "
        "WHERE ss.strategy_id = ? AND g.status = 'shelved' LIMIT 1",
        (strategy_id,),
    ).fetchone()
    if shelved:
        return _DEAD_CAUSE_SUBGOAL_SHELVED
    verify_fail = conn.execute(
        "SELECT 1 FROM dead_attempts "
        "WHERE target_kind = 'Strategy' AND target_id = ? LIMIT 1",
        (strategy_id,),
    ).fetchone()
    if verify_fail:
        return _DEAD_CAUSE_VERIFY
    return None


def _goal_label(goal: sqlite3.Row) -> str:
    bits = [goal["status"]]
    if goal["attempts"]:
        bits.append(f"attempts={goal['attempts']}")
    return f"{goal['slug']}  ({', '.join(bits)})"


def _strategy_label(conn: sqlite3.Connection, strategy: sqlite3.Row) -> str:
    status = strategy["status"]
    if status == "dead":
        cause = _strategy_dead_cause(conn, int(strategy["id"]))
        if cause:
            return f"via s{strategy['id']}  (dead — {cause})"
        return f"via s{strategy['id']}  (dead)"
    return f"via s{strategy['id']}  ({status})"


def _walk_goal(conn: sqlite3.Connection, goal_id: int,
               visited: set[int], lines: list[str], prefix: str) -> None:
    """Recurse a goal and its strategies. `prefix` is the indent string
    BEFORE this node's connector; this function handles only children
    of the given goal. The goal's own line was rendered by the caller."""
    if goal_id in visited:
        # Defensive: under the retired multi-parent model, a goal could in theory be
        # sub-goal of multiple strategies (not currently emitted by
        # Backward, but the schema permits). Show the cycle marker
        # instead of looping forever.
        lines.append(f"{prefix}(... already shown above ...)")
        return
    visited.add(goal_id)

    strategies = conn.execute(
        "SELECT id, goal_id, status FROM strategies "
        "WHERE goal_id = ? ORDER BY id", (goal_id,),
    ).fetchall()

    for i, strat in enumerate(strategies):
        is_last_strat = (i == len(strategies) - 1)
        connector = "└── " if is_last_strat else "├── "
        child_prefix = "    " if is_last_strat else "│   "
        lines.append(f"{prefix}{connector}{_strategy_label(conn, strat)}")

        sub_rows = conn.execute(
            "SELECT g.* FROM strategy_subgoals ss "
            "JOIN goals g ON g.id = ss.subgoal_id "
            "WHERE ss.strategy_id = ? ORDER BY ss.position",
            (int(strat["id"]),),
        ).fetchall()
        for j, sub in enumerate(sub_rows):
            is_last_sub = (j == len(sub_rows) - 1)
            sub_connector = "└── " if is_last_sub else "├── "
            sub_child_prefix = "    " if is_last_sub else "│   "
            lines.append(
                f"{prefix}{child_prefix}{sub_connector}{_goal_label(sub)}"
            )
            _walk_goal(
                conn, int(sub["id"]), visited, lines,
                prefix + child_prefix + sub_child_prefix,
            )


def render(conn: sqlite3.Connection, problem: str) -> str:
    """Build the full TREE.md content for `problem`. Returns the
    string; caller decides where to write it."""
    root = conn.execute(
        "SELECT * FROM goals WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()
    if root is None:
        return f"# {problem} — TREE\n\n(no root goal — run `asterism init {problem}`)\n"

    counts: dict[str, int] = {}
    for r in conn.execute(
        "SELECT status, count(*) c FROM goals WHERE problem = ? GROUP BY status",
        (problem,),
    ):
        counts[r["status"]] = int(r["c"])
    summary_parts = []
    for s in ("proved", "shelved", "attempting", "open"):
        if counts.get(s):
            summary_parts.append(f"{counts[s]} {s}")
    summary = " / ".join(summary_parts) if summary_parts else "(empty)"

    lines = [
        f"# {problem} — TREE",
        "",
        f"_Auto-updated by dispatcher on every cascade._",
        "",
        "```",
        _goal_label(root),
    ]
    _walk_goal(conn, int(root["id"]), set(), lines, "")
    lines.append("```")
    lines.append("")
    lines.append(f"**Counters:** {summary}")
    lines.append("")
    return "\n".join(lines)


def write(conn: sqlite3.Connection, workspace: Path, problem: str) -> Path | None:
    """Write the rendered tree to `Problems/<p>/TREE.md`. Atomic via
    tmp-file + os.replace so a reader never sees a half-written tree.
    Returns the path written, or None if the Problem dir does not exist
    (e.g. this is a unit-test conn with no on-disk Problem)."""
    pdir = db.problem_dir(workspace, problem)
    if not pdir.exists():
        return None
    target = pdir / "TREE.md"
    content = render(conn, problem)
    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp", prefix="TREE.", dir=str(pdir),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        # Best-effort cleanup; never crash the dispatcher over a
        # tree-write hiccup (filesystem race, permission, full disk).
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise
    return target


def write_for_target(conn: sqlite3.Connection, workspace: Path,
                     target_id: str, target_kind: str) -> Path | None:
    """Convenience wrapper for the dispatcher hook: figure out which
    Problem owns the target, then write its tree. No-op if the target
    doesn't map to a known Problem (race on a freshly-deleted goal,
    test fixture without filesystem, etc.). Swallows all exceptions —
    a tree-write failure must never break the dispatcher loop."""
    try:
        if target_kind == "Strategy":
            row = conn.execute(
                "SELECT g.problem FROM strategies s "
                "JOIN goals g ON g.id = s.goal_id WHERE s.id = ?",
                (int(target_id),),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT problem FROM goals WHERE id = ?", (int(target_id),),
            ).fetchone()
        if row is None:
            return None
        return write(conn, workspace, row["problem"])
    except Exception as exc:
        print(f"[tree] write skipped: {exc}", flush=True)
        return None
