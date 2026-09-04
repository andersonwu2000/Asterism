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
  - `goal_events` statuses the schema has since retired are mapped
    forward at the read (`RETIRED_GOAL_STATUSES`), never by rewriting
    the journal;
  - proof files are pruned from the scratch tree on two DB-derived
    rules: the file of a row the rewind deleted, and the file of a
    surviving goal whose proof landed after the cutoff
    (`prune_proof_files` — the scratch's `Problems/` is copied from the
    LIVE tree, so without this a rewound judge reads proofs that did
    not exist yet).
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

#: Statuses `goal_events` still carries that `goals.status` no longer
#: accepts, and what each one is now called.
#:
#: v51 (`8c1aba0d`) retired the goal status `dead` and narrowed the
#: `goals.status` CHECK — and deliberately left the historical journal
#: rows alone ("the history is the point": a park whose origin is
#: invisible is indistinguishable from a threshold shelve). The rewind
#: reads its statuses back OUT of that journal, so on any post-v51 DB
#: with pre-v51 history it wrote `dead` into a column that no longer
#: takes it and died on the CHECK — hit for real on 2026-09-04
#: (`docs/internal/experiments/criterion2_replay_2026-09-04.md` §五.5).
#:
#: The mapping lives HERE, at the read, and not in a migration that
#: rewrites `goal_events.to_status`: rewriting would erase exactly the
#: forensics v51 went out of its way to keep, and every future reader of
#: the journal would see a park that never happened. A retired status
#: that is not in this table stops the rewind loudly rather than
#: silently becoming something else.
RETIRED_GOAL_STATUSES = {"dead": "shelved"}


def _live_status(to_status: str) -> str:
    """A journal status as today's `goals.status` spells it."""
    if to_status in _transitions.GOAL_STATES:
        return to_status
    mapped = RETIRED_GOAL_STATUSES.get(to_status)
    if mapped is None:
        raise RuntimeError(
            f"goal_events carries the status {to_status!r}, which"
            f" `goals.status` no longer accepts and"
            f" `timetravel.RETIRED_GOAL_STATUSES` does not map — add it"
            f" there (with the migration that retired it) rather than"
            f" guessing")
    return mapped


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
            want = _live_status(str(ev["to_status"]))
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
                      workspace: Path, problem: str,
                      cutoff: str) -> list[str]:
    """Make `Problems/<p>/proofs/` match the rewound DB. Two rules, both
    read off the record — never off a file's mtime, which a `copytree`
    rewrites anyway:

      1. the file of a ROW the rewind deleted (a brick or strategy born
         after the cutoff), which would still show in CATALOG / inspect;
      2. the file of a goal that SURVIVED the rewind but whose proof
         landed after it — proved in the snapshot, not proved in the
         rewound DB. At the cutoff that path held a `sorry` stub; on
         disk it holds the finished proof.

    Rule 2 is the 2026-09-04 defect. `run_matrix` and the judge-replay
    scratch builder copy the problem directory from the LIVE tree,
    `rewind` moves the DB only, and this function removed rule-1 files
    only — so a judge rewound to 2026-09-02T23:31Z read
    `L_actual_roots_free_cap_face_matching_or_compressed_core.lean` as a
    landed proof and rebutted the proposal for "re-dispatching landed
    work", eleven hours before that proof existed
    (`docs/internal/experiments/criterion2_replay_2026-09-04.md` §2.3).
    The rewound status is itself the journal's answer (`rewind` step 4),
    so rule 2 introduces no second approximation.

    Files the DB never knew are left alone. KNOWN GAP, not derivable
    from the record: a goal proved BEFORE the cutoff whose file was
    later rewritten (verify-collapse, a Librarian promote) keeps the
    rewritten bytes — the DB journals the status, not the content.

    Returns the removed file names.
    """
    snap = sqlite3.connect(f"file:{Path(snapshot_db).as_posix()}?mode=ro", uri=True)
    snap.row_factory = sqlite3.Row
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
    # Rule 2 — the proof postdates the cutoff. Matched by goal id, not by
    # path: a path the rewind freed and a surviving goal's path are
    # different facts, and rule 1 already owns the first.
    unproved = {int(r[0]) for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND status != 'proved'",
        (problem,))}
    late: list[str] = []
    for r in snap.execute(
            "SELECT id, lean_path, status FROM goals WHERE problem = ?",
            (problem,)):
        if (str(r["status"]) == "proved" and int(r["id"]) in unproved
                and r["lean_path"]):
            late.append(str(r["lean_path"]))
    snap.close()
    removed: list[str] = []
    seen: set[str] = set()
    for rel in gone + late:
        if rel in seen:
            continue
        seen.add(rel)
        p = workspace / rel
        if p.exists():
            p.unlink()
            removed.append(p.name)
    print(f"[timetravel] pruned {len(removed)} file(s) — "
          f"{len(gone)} from deleted rows, {len(late)} proved after "
          f"{cutoff}", flush=True)
    return removed


# ─── scratch workspace ───

COPY_DIRS = ("Tooling", "Library", "Asterism", "Benchmarks")
COPY_FILES = ("lakefile.lean", "lake-manifest.json", "lean-toolchain", "VERSION",
              "Asterism.yaml", ".env")
#: Junctioned into the scratch workspace instead of copied. `Papers`
#: left this list when the shelf retired into `Problems/<project>/_docs/`
#: (§3.9): the documents travel with the problem directories the
#: rewind already copies, so a junction would have pointed the scratch
#: run's papers back at the live tree.
LINK_DIRS = (".lake", ".git")


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
    # The Project's documents — its papers among them (§3.9) — come
    # from the LIVE tree: a rewound wake read them, and a snapshot of a
    # problem directory never held them. Copied, not junctioned: a
    # scratch run that wrote into the real shelf would edit the live
    # workspace, which `build_scratch` promises it never does.
    seg = problem.split(".")[0]
    live_docs = src / "Problems" / seg / "_docs"
    if "." in problem and live_docs.is_dir():
        shutil.copytree(live_docs, dst / "Problems" / seg / "_docs",
                        dirs_exist_ok=True)
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
                                workspace=dst, problem=a.problem,
                                cutoff=a.cutoff)
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
