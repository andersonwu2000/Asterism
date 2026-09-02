"""Rewind a problem's DB state to a cutoff instant (on a COPY) and build
a scratch workspace to replay a historical wake in.

Why (2026-08-30): the wake that minted `fin10_nine_trace_depth_two_
source_bound` (group 504, rev 20, pipeline 74f9e665, 04:11Z 08-26) is
the reference case for "would the NL layer do this again under today's
prompts?". Its codex transcript survives, but the tools an agent uses
(inspect / TREE / CATALOG) read the DB and proofs/ — which have moved
on by 700 goals. A replay therefore needs the DB as it stood then.

The rewind is an APPROXIMATION and says so:
  - rows created after the cutoff are deleted (goals, strategies,
    decisions, revisions, groups, verdicts, pipelines, usage, events);
  - goal statuses are read back from `goal_events` (the last transition
    at or before the cutoff); a goal with no event keeps its status
    unless that status is terminal, then `open`;
  - a `succeeded`/`superseded` strategy whose goal is no longer proved
    falls back to `proposed` (strategy history is not journaled);
  - groups touched after the cutoff go back to `active`; the routine /
    strategist clocks go back to the group's last surviving commit;
  - proof files of the deleted rows are pruned from the scratch tree.
It refuses to open the live database (`open_copy_for_rewind`).
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from Tooling.state import db, groups
from Tooling.state import transitions as _transitions

TERMINAL = _transitions.GOAL_TERMINALS


def _looks_live(path: Path) -> bool:
    """The workspace's own asterism.db, or one with a live daemon.pid
    beside it, is live."""
    p = Path(path).resolve()
    if p == (Path.cwd() / "asterism.db").resolve():
        return True
    pid_file = p.parent / ".asterism" / "daemon.pid"
    try:
        pid = int(pid_file.read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return False
    from ..core.dispatcher.lock import _pid_alive
    return _pid_alive(pid)


def open_copy_for_rewind(path: Path) -> sqlite3.Connection:
    if _looks_live(Path(path)):
        raise RuntimeError(f"{path} looks like a live database — rewind a copy")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def rewind(conn: sqlite3.Connection, *, problem: str, cutoff: str) -> dict:
    """Rewind `problem` to `cutoff` (ISO-8601 UTC, compared as text the
    way the tables store it). Returns counts."""
    rep: dict = {}
    conn.execute("PRAGMA foreign_keys = OFF")
    # 1. goals born after the cutoff, with everything hanging off them
    new_goals = [int(r[0]) for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND created_at > ?", (problem, cutoff))]
    if new_goals:
        marks = ",".join("?" * len(new_goals))
        sids = [int(r[0]) for r in conn.execute(
            f"SELECT id FROM strategies WHERE goal_id IN ({marks})", new_goals)]
        if sids:
            sm = ",".join("?" * len(sids))
            conn.execute(f"DELETE FROM strategy_subgoals WHERE strategy_id IN ({sm})", sids)
            conn.execute(f"DELETE FROM strategies WHERE id IN ({sm})", sids)
        conn.execute(f"DELETE FROM strategy_subgoals WHERE subgoal_id IN ({marks})", new_goals)
        conn.execute(f"DELETE FROM goal_events WHERE goal_id IN ({marks})", new_goals)
        conn.execute(f"DELETE FROM goals WHERE id IN ({marks})", new_goals)
    rep["goals_deleted"] = len(new_goals)
    # 2. strategies born after the cutoff on surviving goals
    new_strats = [int(r[0]) for r in conn.execute(
        "SELECT s.id FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE g.problem = ? AND s.created_at > ?", (problem, cutoff))]
    if new_strats:
        sm = ",".join("?" * len(new_strats))
        conn.execute(f"DELETE FROM strategy_subgoals WHERE strategy_id IN ({sm})", new_strats)
        conn.execute(f"DELETE FROM strategies WHERE id IN ({sm})", new_strats)
    rep["strategies_deleted"] = len(new_strats)
    # 3. problem-keyed history after the cutoff
    for table, col in (("strategist_decisions", "created_at"),
                       ("programme_revisions", "created_at"),
                       ("routine_verdicts", "created_at"),
                       ("kb_entries", "created_at"),
                       ("spawn_usage", "ts")):
        try:
            cur = conn.execute(f"DELETE FROM {table} WHERE problem = ? AND {col} > ?",
                               (problem, cutoff))
            rep[f"{table}_deleted"] = cur.rowcount
        except sqlite3.OperationalError:
            rep[f"{table}_deleted"] = None
    cur = conn.execute("DELETE FROM groups WHERE problem = ? AND created_at > ?", (problem, cutoff))
    rep["groups_deleted"] = cur.rowcount
    conn.execute("DELETE FROM queue WHERE problem = ?", (problem,))
    try:
        conn.execute("DELETE FROM pipelines WHERE started_at > ?", (cutoff,))
        conn.execute("DELETE FROM dead_attempts WHERE ts > ?", (cutoff,))
    except sqlite3.OperationalError:
        pass
    # 4. goal statuses back from the event journal
    rewound = 0
    for g in conn.execute("SELECT id, status, origin FROM goals WHERE problem = ?", (problem,)).fetchall():
        ev = conn.execute(
            "SELECT to_status FROM goal_events WHERE goal_id = ? AND at <= ?"
            " ORDER BY at DESC, id DESC LIMIT 1", (int(g["id"]), cutoff)).fetchone()
        if ev is not None:
            want = str(ev["to_status"])
        elif str(g["status"]) in TERMINAL and str(g["origin"]) != "root":
            want = "open"
        else:
            continue
        if want != str(g["status"]):
            # The checked mutator appends a goal_events row stamped now();
            # the journal trim two lines down removes it with the rest of
            # the post-cutoff history.
            db.update_goal_status(conn, int(g["id"]), want, event="timetravel_rewind",
                                  reason=f"rewound to {cutoff}")
            rewound += 1
    rep["goals_rewound"] = rewound
    conn.execute("DELETE FROM goal_events WHERE problem = ? AND at > ?", (problem, cutoff))
    # 5. strategies whose goal is no longer proved cannot have won
    won = conn.execute(
        "SELECT id FROM strategies WHERE status IN ('succeeded', 'superseded')"
        " AND goal_id IN (SELECT id FROM goals WHERE problem = ? AND status != 'proved')",
        (problem,)).fetchall()
    for row in won:
        db.update_strategy_status(conn, int(row["id"]), "proposed")  # non-terminal: no hook
    rep["strategies_rewound"] = len(won)
    # 6. groups and clocks
    closed = conn.execute(
        "SELECT id FROM groups WHERE problem = ? AND updated_at > ?"
        " AND status IN ('closed', 'returned', 'delivered')", (problem, cutoff)).fetchall()
    for row in closed:
        groups.rewind_status(conn, int(row["id"]), "active")
    rep["groups_reopened"] = len(closed)
    # The clocks are the batch-acknowledgement ratchets the trigger
    # derivation reads: clamping them to the cutoff would make a batch
    # resolved just before it look acknowledged (the replay would derive
    # `routine`, not the `inject_batch_done` the original wake had). A
    # touched clock goes back to the group's last SURVIVING strategist
    # commit; a group with none keeps NULL semantics via the cutoff.
    for g in conn.execute("SELECT id FROM groups WHERE problem = ?", (problem,)).fetchall():
        gid = int(g["id"])
        last = conn.execute(
            "SELECT MAX(created_at) FROM strategist_decisions"
            " WHERE problem = ? AND group_id = ?", (problem, gid)).fetchone()[0]
        anchor = str(last) if last else cutoff
        for col in ("last_routine_at", "last_strategist_at"):
            conn.execute(f"UPDATE groups SET {col} = ? WHERE id = ? AND {col} > ?",
                         (anchor, gid, cutoff))
    last_p = conn.execute(
        "SELECT MAX(created_at) FROM strategist_decisions WHERE problem = ?",
        (problem,)).fetchone()[0]
    for col in ("last_routine_at", "last_strategist_at"):
        try:
            conn.execute(f"UPDATE problems SET {col} = ? WHERE name = ? AND {col} > ?",
                         (str(last_p) if last_p else cutoff, problem, cutoff))
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return rep


def prune_proof_files(conn: sqlite3.Connection, *, snapshot_db: Path,
                      workspace: Path, problem: str) -> list[str]:
    """Delete the proof files of rows the rewind removed, so disk matches
    the rewound DB (a brick or strategy file born after the cutoff would
    still show in CATALOG / inspect). Files the DB never knew are left
    alone. Returns the removed file names."""
    snap = sqlite3.connect(f"file:{Path(snapshot_db).as_posix()}?mode=ro", uri=True)
    live_goal_paths = {str(r[0]) for r in conn.execute(
        "SELECT lean_path FROM goals WHERE problem = ?", (problem,))}
    live_strat_paths = {str(r[0]) for r in conn.execute(
        "SELECT s.scratch_path FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE g.problem = ? AND s.scratch_path IS NOT NULL", (problem,))}
    gone: list[str] = []
    for r in snap.execute("SELECT lean_path FROM goals WHERE problem = ?", (problem,)):
        if str(r[0]) not in live_goal_paths:
            gone.append(str(r[0]))
    for r in snap.execute(
            "SELECT s.scratch_path FROM strategies s JOIN goals g ON g.id = s.goal_id"
            " WHERE g.problem = ? AND s.scratch_path IS NOT NULL", (problem,)):
        if str(r[0]) not in live_strat_paths:
            gone.append(str(r[0]))
    snap.close()
    removed: list[str] = []
    for rel in gone:
        p = workspace / rel
        if p.exists():
            p.unlink()
            removed.append(p.name)
    return removed


# ─── scratch workspace ───

COPY_DIRS = ("Tooling", "Library", "Asterism", "Benchmarks")
COPY_FILES = ("lakefile.lean", "lake-manifest.json", "lean-toolchain", "VERSION",
              "Asterism.yaml", ".env")
LINK_DIRS = (".lake", "Papers", ".git")


def _link_dir(src: Path, dst: Path) -> None:
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                       check=True, capture_output=True)
    else:
        os.symlink(src, dst, target_is_directory=True)


def refresh_derived_files(conn: sqlite3.Connection, *, workspace: Path,
                          problem: str) -> "list[Path]":
    """Re-derive the rendered files the DB owns — `TREE.md` and every
    group's `PROGRAMME.md` — so the scratch workspace shows the rewound
    scene, not the snapshot's. Both sides' round companions are re-rendered
    from this DB every round and the agents grep them in place: the
    first experiment-3
    run (2026-08-30) was judged against a TREE that still listed the
    goal the proposal was about to mint."""
    from Tooling.state import programme, tree
    written: list[Path] = []
    t = tree.write(conn, workspace, problem)
    if t is not None:
        written.append(t)
    pdir = db.problem_dir(workspace, problem)
    if pdir.exists():
        for row in conn.execute("SELECT id FROM groups WHERE problem = ?", (problem,)):
            out = programme.render(conn, problem, pdir, int(row["id"]))
            if out is not None:
                written.append(out)
    return written


def build_scratch(*, src: Path, dst: Path, snapshot_db: Path,
                  snapshot_problem_dir: Path, problem: str) -> None:
    """A workspace beside the real one: code and config COPIED, the
    heavy read-only trees LINKED, the problem and DB taken from the
    snapshot. Never touches `src`."""
    dst.mkdir(parents=True, exist_ok=False)
    for d in COPY_DIRS:
        if (src / d).exists():
            shutil.copytree(src / d, dst / d, ignore=shutil.ignore_patterns("__pycache__"))
    for f in COPY_FILES:
        if (src / f).exists():
            shutil.copy2(src / f, dst / f)
    for d in LINK_DIRS:
        if (src / d).exists():
            _link_dir(src / d, dst / d)
    (dst / ".asterism").mkdir()
    (dst / ".attempts").mkdir()
    pdir = dst / "Problems" / Path(*problem.split("."))
    shutil.copytree(snapshot_problem_dir, pdir)
    shutil.copy2(snapshot_db, dst / "asterism.db")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=".", help="the real workspace (read-only)")
    ap.add_argument("--dst", required=True, help="scratch workspace to create")
    ap.add_argument("--snapshot", required=True,
                    help="dir holding asterism.db and <problem leaf dir> from a backup")
    ap.add_argument("--problem", required=True)
    ap.add_argument("--cutoff", required=True, help="ISO-8601 UTC instant")
    a = ap.parse_args(argv)
    src, dst, snap = Path(a.src).resolve(), Path(a.dst).resolve(), Path(a.snapshot).resolve()
    leaf = a.problem.split(".")[-1]
    build_scratch(src=src, dst=dst, snapshot_db=snap / "asterism.db",
                  snapshot_problem_dir=snap / leaf, problem=a.problem)
    conn = open_copy_for_rewind(dst / "asterism.db")
    rep = rewind(conn, problem=a.problem, cutoff=a.cutoff)
    print("[timetravel] rewind:", rep)
    removed = prune_proof_files(conn, snapshot_db=snap / "asterism.db",
                                workspace=dst, problem=a.problem)
    print(f"[timetravel] pruned {len(removed)} post-cutoff proof file(s)")
    written = refresh_derived_files(conn, workspace=dst, problem=a.problem)
    print(f"[timetravel] re-derived {len(written)} rendered file(s) (TREE.md, PROGRAMME.md)")
    for k, v in (("goals", conn.execute("SELECT COUNT(*) FROM goals WHERE problem=?", (a.problem,)).fetchone()[0]),
                 ("max decision", conn.execute("SELECT MAX(id) FROM strategist_decisions WHERE problem=?", (a.problem,)).fetchone()[0]),
                 ("max rev row", conn.execute("SELECT MAX(id) FROM programme_revisions WHERE problem=?", (a.problem,)).fetchone()[0])):
        print(f"[timetravel] {k}: {v}")
    conn.close()
    print(f"[timetravel] scratch workspace ready: {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
