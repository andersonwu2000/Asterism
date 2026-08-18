"""Per-Problem AND/OR proof tree renderer.

`Problems/<p>/TREE.md` is the canonical human-facing view of a Problem's
proof progress. Auto-updated by the dispatcher on every cascade so the
file always reflects the latest state — readers can leave it open in
an editor / file watcher.

File order is live-first (2026-08-15, from a three-corpus transcript
survey of what readers actually ask this file): counters, then `## Root`,
then one section per non-empty non-proved status listing each goal with
its ancestor path, then `## Lemmas` (the full relationship record). The
dominant reads are point status checks and non-proved censuses; a
default read that budgets out mid-file must therefore meet the live
material first, not the proved history.

    **Counters:** 12 proved / 2 shelved / 1 open

    ## Root

    ```
    main [g1]  (attempting, attempts=1)
    ├─ via s15  (dead — sub-goal shelved)
    │  ├─ s15_sub_1 [g4]  (shelved, attempts=8)
    │  └─ s15_sub_2 [g5]  (attempting)
    └─ via s36  (proposed — OR retry)
    ```

    ## Shelved

    - s15_sub_1 [g4]  (attempts=8)  — main › s15

    ## Lemmas

    ```
    contour_lemma [g9]  (proved)
    └─ via s18  (succeeded)
       └─ contour_sub [g10]  (proved)
    ```

`via sNN` lines are Strategy nodes (the AND layer); their children
are sub-Goals. A Goal can have multiple Strategies (OR alternatives),
all rendered as siblings under the Goal.

Goals carry BOTH identifiers: the slug (the semantic name every other
surface greps by) and `[gNNNN]` (the DB id that decision annotations
use) — readers arrive with either key, and before 2026-08-15 the
numeric-key greps silently missed.
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
# names to cross-reference with active_goals_sidecar).
_BRANCH_LAST = "└─ "
_BRANCH_MID = "├─ "
_PAD_LAST = "   "
_PAD_MID = "│  "

# Live/settled partition of goal states. The frontier RENDER that
# consumed this is gone (2026-07-13: the Strategist's inline tree became
# a summary header + on-demand TREE.md read, so the collapse-for-context
# optimization lost its purpose), but the partition itself remains the
# documented invariant — test_transitions binds LIVE ∪ SETTLED to the
# goal-state enum so a new status must consciously pick a side.
_LIVE_GOAL_STATUSES = frozenset(
    {"open", "attempting", "pending_strategist_review"})
_SETTLED_GOAL_STATUSES = frozenset(
    {"proved", "shelved", "disproved", "dead", "frozen"})


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


# One section per non-proved status, live states first. Statuses the
# tuple does not know still render (under their raw enum name) — a new
# status must never silently vanish from the census.
_STATUS_SECTION_ORDER = (
    ("attempting", "Attempting"),
    ("open", "Open"),
    ("pending_strategist_review", "Pending review"),
    ("shelved", "Shelved"),
    ("frozen", "Frozen"),
    ("disproved", "Disproved"),
    ("dead", "Dead"),
)


def _goal_label(goal: sqlite3.Row) -> str:
    bits = [goal["status"]]
    if goal["attempts"]:
        bits.append(f"attempts={goal['attempts']}")
    return f"{goal['slug']} [g{goal['id']}]  ({', '.join(bits)})"


def _ancestor_path(conn: sqlite3.Connection, goal_id: int) -> str:
    """`main › s24216 › frankl_core` — the chain ABOVE a goal, root
    first, self excluded. This is the line that answers the two
    high-consequence questions readers historically dug out of the
    ASCII indentation: whose subtree is this node in (group ownership)
    and would shelving X cascade onto it. Multi-parent is not emitted
    by Backward; take the first edge, guard against cycles anyway."""
    parts: list[str] = []
    cur = goal_id
    seen: set[int] = set()
    while cur not in seen:
        seen.add(cur)
        row = conn.execute(
            "SELECT ss.strategy_id AS sid, s.goal_id AS pid, g.slug AS pslug"
            " FROM strategy_subgoals ss"
            " JOIN strategies s ON s.id = ss.strategy_id"
            " JOIN goals g ON g.id = s.goal_id"
            " WHERE ss.subgoal_id = ? ORDER BY ss.strategy_id LIMIT 1",
            (cur,),
        ).fetchone()
        if row is None:
            break
        parts.append(f"s{row['sid']}")
        parts.append(str(row["pslug"]))
        cur = int(row["pid"])
    parts.reverse()
    return " › ".join(parts)


def _status_sections(conn: sqlite3.Connection, problem: str) -> list[str]:
    """The by-status census: every non-proved goal, one line, with its
    ancestor path. Status itself lives in the heading (not repeated per
    line); an absent section means that status is empty."""
    rows = conn.execute(
        "SELECT id, slug, status, attempts, origin FROM goals"
        " WHERE problem = ? AND status != 'proved' ORDER BY id",
        (problem,),
    ).fetchall()
    by_status: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        by_status.setdefault(str(r["status"]), []).append(r)

    def _line(r: sqlite3.Row) -> str:
        path = _ancestor_path(conn, int(r["id"]))
        if not path:
            path = ("root goal" if r["origin"] == "root"
                    else "standalone lemma" if r["origin"] == "forward"
                    else "(unlinked)")
        att = f"  (attempts={r['attempts']})" if r["attempts"] else ""
        return f"- {r['slug']} [g{r['id']}]{att}  — {path}"

    out: list[str] = []
    titled = {k: t for k, t in _STATUS_SECTION_ORDER}
    ordered = [k for k, _ in _STATUS_SECTION_ORDER if k in by_status]
    ordered += sorted(k for k in by_status if k not in titled)
    for key in ordered:
        out += ["", f"## {titled.get(key, key)}", ""]
        out += [_line(r) for r in by_status[key]]
    return out


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
        for j, sub in enumerate(sub_rows):
            is_last_sub = (j == len(sub_rows) - 1)
            sub_connector = _BRANCH_LAST if is_last_sub else _BRANCH_MID
            sub_child_prefix = _PAD_LAST if is_last_sub else _PAD_MID
            lines.append(
                f"{prefix}{child_prefix}{sub_connector}{_goal_label(sub)}"
            )
            _walk_goal(
                conn, int(sub["id"]), visited, lines,
                prefix + child_prefix + sub_child_prefix,
            )


def _stamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def render(conn: sqlite3.Connection, problem: str) -> str:
    """Build the TREE.md content for `problem` — the full tree, every
    node expanded. Returns the string; caller decides where to write it.
    (The frontier=True collapsed variant was deleted 2026-07-13: its
    sole consumer, the Strategist's inline tree, became a summary header
    that points at this full render on disk.)"""
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
    counter_order = ["proved"] + [k for k, _ in _STATUS_SECTION_ORDER]
    counter_order += sorted(k for k in counts if k not in counter_order)
    summary_parts = [
        f"{counts[s]} {s}" for s in counter_order if counts.get(s)]
    summary = " / ".join(summary_parts) if summary_parts else "(empty)"

    lines = [
        f"# {problem} — TREE",
        "",
        # AS-OF, not just provenance. Several readers compare this
        # file against a live `inspect`, and one of them is a judge
        # deciding a verdict; with no timestamp a disagreement
        # reads as a defect in whoever quoted the other one
        # (08-13 judge report).
        f"_Written {_stamp()} by the dispatcher, which rewrites it"
        f" on every cascade. The record is the DB —"
        ' `inspect({"decl": "<slug>"})` reads it live._',
        "",
        # Full census up front — the by-status sections below list only
        # the non-empty statuses, so this line is where "nothing
        # shelved" is stated rather than implied.
        f"**Counters:** {summary}",
    ]
    visited: set[int] = set()
    if root is not None:
        lines += ["", "## Root", "", "```", _goal_label(root)]
        _walk_goal(conn, int(root["id"]), visited, lines, "")
        lines.append("```")
    else:
        # Phase 6 pure-NL: no root goal — the problem is a forest of
        # Forward-origin trees (rendered below). A brand-new problem has
        # no goals at all yet; say so instead of implying a broken init.
        lines += ["", "_(pure-NL problem — no root goal; standalone "
                  "lemmas below)_"]

    lines += _status_sections(conn, problem)

    # Forward-origin goals are independent lemmas (no parent strategy
    # edge to root). Render each as its own sub-tree under a separate
    # `## Lemmas` header so they're visible alongside the main
    # decomposition. Backward sub-trees attached below a Forward goal
    # are walked through the same `_walk_goal` (each Forward goal is a
    # local root). See docs/archive/design/phase2/design.md §3 — Forward lemmas are
    # standalone tools the rest of the proof can reach for via dedupe.
    # Last in the file: by this point the roster is >90% proved history,
    # and the live material above must survive a budgeted default read.
    forward_roots = conn.execute(
        "SELECT * FROM goals WHERE problem = ? AND origin = 'forward' "
        "ORDER BY id", (problem,),
    ).fetchall()
    if forward_roots:
        lines += ["", "## Lemmas", "", "```"]
        for fg in forward_roots:
            lines.append(_goal_label(fg))
            _walk_goal(conn, int(fg["id"]), visited, lines, "")
            lines.append("")
        # Strip the trailing blank inside the fenced block.
        if lines[-1] == "":
            lines.pop()
        lines.append("```")

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
