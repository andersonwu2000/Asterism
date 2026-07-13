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

# 2-char indent (vs 4) halves horizontal growth per nesting level —
# the difference between a wrapping sl2 tree and a readable one at
# typical editor widths. Slugs themselves stay full-length (the
# Strategist agent reads TREE.md inline and needs unambiguous slug
# names to cross-reference with active_goals_sidecar / Manifest).
_BRANCH_LAST = "└─ "
_BRANCH_MID = "├─ "
_PAD_LAST = "   "
_PAD_MID = "│  "

# Frontier view (the Strategist's inline tree, framework_backlog #2): a
# goal is part of the live planning frontier when it — or a descendant —
# can still be worked. SETTLED subtrees collapse to a single labelled
# line (slug + status kept, so cite / Reopen decisions still see them).
# 'dead'/'frozen'/'disproved' are terminals; 'shelved' is soft-parked but
# off the frontier, so it collapses too (one line is enough to spot a
# Reopen candidate). The full, uncollapsed tree is always on disk in
# TREE.md — the inline view links to it as an escape hatch.
_LIVE_GOAL_STATUSES = frozenset(
    {"open", "attempting", "pending_strategist_review"})
_SETTLED_GOAL_STATUSES = frozenset(
    {"proved", "shelved", "disproved", "dead", "frozen"})


def _subtree_is_live(conn: sqlite3.Connection, goal_id: int,
                     memo: dict[int, bool],
                     _guard: set[int] | None = None) -> bool:
    """True iff `goal_id` — or any descendant goal/strategy — is still an
    active planning frontier (a live goal status, or an in-flight
    `proposed` strategy anywhere below). The frontier view uses this to
    decide whether a settled-looking subtree actually hides live work
    (e.g. a goal revived shelved→open by a citation under an otherwise
    dead strategy) before collapsing it. Memoized for the whole render;
    `_guard` breaks the schema-permitted shared-subgoal cycle by
    returning False on the back-edge (real Backward output is acyclic, so
    this only matters for the defensive multi-parent case)."""
    if goal_id in memo:
        return memo[goal_id]
    if _guard is None:
        _guard = set()
    if goal_id in _guard:
        return False
    _guard.add(goal_id)
    row = conn.execute(
        "SELECT status FROM goals WHERE id = ?", (goal_id,)).fetchone()
    live = bool(row) and row["status"] in _LIVE_GOAL_STATUSES
    if not live:
        for s in conn.execute(
            "SELECT id, status FROM strategies WHERE goal_id = ?",
            (goal_id,),
        ).fetchall():
            if s["status"] == "proposed":
                live = True
                break
            for sub in conn.execute(
                "SELECT subgoal_id FROM strategy_subgoals "
                "WHERE strategy_id = ?", (int(s["id"]),),
            ).fetchall():
                if _subtree_is_live(
                        conn, int(sub["subgoal_id"]), memo, _guard):
                    live = True
                    break
            if live:
                break
    _guard.discard(goal_id)
    memo[goal_id] = live
    return live


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
               visited: set[int], lines: list[str], prefix: str, *,
               frontier: bool = False,
               live_memo: dict[int, bool] | None = None) -> None:
    """Recurse a goal and its strategies. `prefix` is the indent string
    BEFORE this node's connector; this function handles only children
    of the given goal. The goal's own line was rendered by the caller.

    When `frontier` is set (the Strategist inline view), SETTLED subtrees
    are pruned: an abandoned strategy (dead/disproved) and a settled
    sub-goal (proved/shelved/dead/disproved/frozen) each collapse to their
    own already-rendered label line, skipping their children — UNLESS the
    subtree still hides live work (`_subtree_is_live`), in which case it is
    walked normally so the live frontier is never buried or dropped."""
    if live_memo is None:
        live_memo = {}
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
    # Childless succeeded strategies (a Backward leaf-bypass / in-place
    # proof) render as pure noise under an already-proved goal — the
    # `via sNN (succeeded)` line carries no structure and no decision
    # value (user call 2026-07-13). Succeeded strategies WITH sub-goals
    # stay: they are the decomposition skeleton.
    strategies = [
        s for s in strategies
        if s["status"] != "succeeded" or conn.execute(
            "SELECT 1 FROM strategy_subgoals WHERE strategy_id = ? LIMIT 1",
            (int(s["id"]),)).fetchone() is not None
    ]

    for i, strat in enumerate(strategies):
        is_last_strat = (i == len(strategies) - 1)
        connector = _BRANCH_LAST if is_last_strat else _BRANCH_MID
        child_prefix = _PAD_LAST if is_last_strat else _PAD_MID
        lines.append(f"{prefix}{connector}{_strategy_label(conn, strat)}")

        sub_rows = conn.execute(
            "SELECT g.* FROM strategy_subgoals ss "
            "JOIN goals g ON g.id = ss.subgoal_id "
            "WHERE ss.strategy_id = ? ORDER BY ss.position",
            (int(strat["id"]),),
        ).fetchall()
        # Frontier prune: an abandoned strategy collapses to its line
        # unless one of its sub-goal subtrees is still live.
        if (frontier and strat["status"] in ("dead", "disproved")
                and not any(_subtree_is_live(conn, int(s["id"]), live_memo)
                            for s in sub_rows)):
            continue
        for j, sub in enumerate(sub_rows):
            is_last_sub = (j == len(sub_rows) - 1)
            sub_connector = _BRANCH_LAST if is_last_sub else _BRANCH_MID
            sub_child_prefix = _PAD_LAST if is_last_sub else _PAD_MID
            lines.append(
                f"{prefix}{child_prefix}{sub_connector}{_goal_label(sub)}"
            )
            # Frontier prune: a settled sub-goal collapses to its label
            # line (no children walked). A 'proved' goal is terminal — any
            # descendant is moot (e.g. a leftover OR-alternative), so it
            # collapses unconditionally. The softer terminals
            # (shelved/dead/disproved/frozen) stay expanded only when their
            # subtree still hides live work (e.g. a cite-revived goal).
            if frontier and sub["status"] in _SETTLED_GOAL_STATUSES and (
                    sub["status"] == "proved"
                    or not _subtree_is_live(conn, int(sub["id"]), live_memo)):
                continue
            _walk_goal(
                conn, int(sub["id"]), visited, lines,
                prefix + child_prefix + sub_child_prefix,
                frontier=frontier, live_memo=live_memo,
            )


def render(conn: sqlite3.Connection, problem: str, *,
           frontier: bool = False) -> str:
    """Build the TREE.md content for `problem`. Returns the string;
    caller decides where to write it.

    `frontier=False` (default, the on-disk human-facing TREE.md): the
    full tree, every node expanded. `frontier=True` (the Strategist
    inline view, `phase2_context._section_tree_inline`): settled subtrees
    collapse to one line each so the live frontier stands out — see
    `_walk_goal` / `_subtree_is_live`."""
    root = conn.execute(
        "SELECT * FROM goals WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()

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

    subtitle = (
        "_Live frontier — settled (proved / shelved / dead) subtrees "
        "collapsed to one line; read TREE.md on disk for the full tree._"
        if frontier else
        "_Auto-updated by dispatcher on every cascade._")
    lines = [
        f"# {problem} — TREE",
        "",
        subtitle,
        "",
    ]
    visited: set[int] = set()
    live_memo: dict[int, bool] = {}
    if root is not None:
        lines += ["```", _goal_label(root)]
        _walk_goal(conn, int(root["id"]), visited, lines, "",
                   frontier=frontier, live_memo=live_memo)
        lines.append("```")
    else:
        # Phase 6 pure-NL: no root goal — the problem is a forest of
        # Forward-origin trees (rendered below). A brand-new problem has
        # no goals at all yet; say so instead of implying a broken init.
        lines.append("_(pure-NL problem — no root goal; deliverable "
                     "forest below)_")

    # Forward-origin goals are independent lemmas (no parent strategy
    # edge to root). Render each as its own sub-tree under a separate
    # `## Forward` header so they're visible alongside the main
    # decomposition. Backward sub-trees attached below a Forward goal
    # are walked through the same `_walk_goal` (each Forward goal is a
    # local root). See docs/archive/design/phase2/design.md §3 — Forward lemmas are
    # standalone tools the rest of the proof can reach for via dedupe.
    forward_roots = conn.execute(
        "SELECT * FROM goals WHERE problem = ? AND origin = 'forward' "
        "ORDER BY id", (problem,),
    ).fetchall()
    if forward_roots:
        lines += ["", "## Forward", "", "```"]
        for fg in forward_roots:
            lines.append(_goal_label(fg))
            _walk_goal(conn, int(fg["id"]), visited, lines, "",
                       frontier=frontier, live_memo=live_memo)
            lines.append("")
        # Strip the trailing blank inside the fenced block.
        if lines[-1] == "":
            lines.pop()
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
    a tree-write failure must never break the dispatcher loop.

    target_kind dispatch:
      - 'Goal'     — int(target_id) → goals.id → problem name
      - 'Strategy' — int(target_id) → strategies.id → goal → problem
      - 'Problem'  — target_id IS the problem name (Forward pipelines,
                      see docs/archive/design/phase2/pipelines.md §4.1). Don't int()
                      it; Phase 2 introduced this target_kind and the
                      original branch only handled Goal/Strategy.
    """
    try:
        if target_kind == "Problem":
            row = conn.execute(
                "SELECT name AS problem FROM problems WHERE name = ?",
                (target_id,),
            ).fetchone()
        elif target_kind == "Strategy":
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
