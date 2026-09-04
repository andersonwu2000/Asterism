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
    not exist yet);
  - every OTHER file surface an agent reads is pruned the same way
    (`rewind_files`): the Project's documents (`_docs/{user,agent}` —
    the judge's `{papers_dir}`), the run-scoped scratch (`.drafts`,
    `.presearch`, `.groups`) and the rendered `PROGRAMME.md` / `TREE.md`,
    which are re-derived from the rewound DB rather than kept.
It refuses to open the live database (`open_copy_for_rewind`).

Every directory it touches produces one ledger line — kept, dropped,
and WHICH provenance signal decided — printed in the rewind output and
written into the scratch as `_rewind_ledger.json`. The signal matters
more than the count: `_docs/user/` is the owner's own writing and has no
DB row anywhere, so it is dated off git when the workspace is a checkout
and off mtime otherwise, and a reader who cannot tell which was used
cannot tell how much to trust the scene.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

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
    # `theory_documents` and `problem_papers` are here because they are
    # the DB half of a FILE the next wake reads: an accepted theory
    # document lands in `_docs/agent/` and a fetched paper in
    # `_docs/<area>/papers/<id>/`. Deleting the row is what lets
    # `prune_project_docs` date the file off the record instead of off
    # an mtime `copytree` rewrites.
    for table, col in (("strategist_decisions", "created_at"),
                       ("programme_revisions", "created_at"),
                       ("routine_verdicts", "created_at"),
                       ("kb_entries", "created_at"),
                       ("theory_documents", "created_at"),
                       ("problem_papers", "created_at"),
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


# ─── dating a file the DB does not own ───
#
# `proofs/` is derivable from the record; the rest of what an agent
# reads is not. `_docs/user/` is the owner's own writing, `.drafts/` is
# a REWRITE-by-contract note, and neither has a row anywhere. Two
# signals answer "when was this written", in this order:
#
#   git   — the commit date of the last commit that touched the file.
#           Survives a `copytree`, which is why it is asked first.
#   mtime — what is left. `shutil.copy2` preserves it, so a scratch
#           built by `build_scratch` / `run_matrix` still carries the
#           live tree's times; a file written INTO the scratch does not.
#
# A file neither can date is dropped and named in the ledger's
# `undated` list. That is the deliberately conservative side: a judge
# reading nothing is safer than a judge reading the future.

#: What decided a file's fate, most authoritative first. Ledger rows
#: report the set actually used, joined with `+`.
PROV_NONE = "none"


def _parse_iso(text: "str | None") -> "datetime | None":
    """An ISO-8601 instant, naive strings read as UTC (the DB's own
    convention — every `created_at` in this schema is UTC)."""
    if not text:
        return None
    s = str(text).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _cutoff_dt(cutoff: str) -> datetime:
    dt = _parse_iso(cutoff)
    if dt is None:
        raise RuntimeError(
            f"cutoff {cutoff!r} is not an ISO-8601 instant — the file"
            f" rewind compares real times, not text, and cannot guess"
            f" what this means")
    return dt


@functools.lru_cache(maxsize=256)
def _git_tracked(workspace: str, rel_dir: str) -> "frozenset[str]":
    """The paths git knows about under `rel_dir`, empty when the
    workspace is not a checkout.

    One `ls-files` per directory, so the per-file `git log` below runs
    only for files that can actually answer. Without it a `.presearch/`
    with 200 entries would be 200 subprocesses to learn that none of
    them is tracked."""
    try:
        out = subprocess.run(
            ["git", "-C", workspace, "ls-files", "-z", "--", rel_dir],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if out.returncode != 0:
        return frozenset()
    return frozenset(p for p in out.stdout.split("\0") if p)


def _git_iso(workspace: Path, rel: str) -> "str | None":
    """When the file is tracked, the date of the last commit that
    touched it. None when the workspace is not a checkout, git is not
    on PATH, or the file was never committed (the common case for
    `_docs/` and the run-scoped scratch, both untracked)."""
    parent = PurePosixPath(rel).parent.as_posix()
    if rel not in _git_tracked(str(Path(workspace)), parent):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(Path(workspace)), "log", "-1", "--format=%cI",
             "--", rel],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def _mtime_iso(path: Path) -> "str | None":
    try:
        st = path.stat()
    except OSError:
        return None
    return datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()


def _file_provenance(workspace: Path, rel: str) -> "tuple[datetime | None, str]":
    """(when the file was written, which signal said so)."""
    iso = _git_iso(workspace, rel)
    if iso is not None:
        dt = _parse_iso(iso)
        if dt is not None:
            return dt, "git"
    iso = _mtime_iso(Path(workspace) / rel)
    if iso is not None:
        dt = _parse_iso(iso)
        if dt is not None:
            return dt, "mtime"
    return None, PROV_NONE


class _Ledger:
    """One directory's row: what stayed, what went, and on what signal.

    The signal set is the point of the row. A directory whose whole
    answer came from `theory_documents` is a rewound directory; one that
    says `mtime` is an approximation, and the report that quotes it has
    to say so."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.kept = 0
        self.dropped: "list[str]" = []
        self.sources: "set[str]" = set()
        self.undated: "list[str]" = []

    def _note(self, source: str) -> None:
        # An entry can be decided by two signals at once (a live id AND
        # a date). Store the ATOMS: joining the composite strings would
        # render `goal_id+mtime` and `goal_id` as
        # `goal_id+mtime+goal_id`, which reads like a third signal.
        self.sources.update(s for s in source.split("+") if s)

    def keep(self, source: str) -> None:
        self.kept += 1
        self._note(source)

    def drop(self, rel: str, source: str) -> None:
        self.dropped.append(rel)
        self._note(source)
        if source == PROV_NONE:
            self.undated.append(rel)

    def as_row(self) -> dict:
        return {"kept": self.kept, "dropped": len(self.dropped),
                "provenance": "+".join(sorted(self.sources)) or "absent",
                "dropped_entries": sorted(self.dropped),
                "undated": sorted(self.undated)}


def _rel(workspace: Path, path: Path) -> str:
    return path.relative_to(Path(workspace)).as_posix()


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            pass


# ─── the Project's documents ───

#: `pipeline: <id>` in the provenance comment `theorist/landing.header`
#: opens every landed theory document with. The row is the first
#: answer; this is the second, for a document written before
#: `theory_documents` existed (v52) or whose row the snapshot lost.
_HEADER_PIPELINE_RE = re.compile(r"^pipeline:\s*(\S+)\s*$", re.MULTILINE)
#: How far into a document the header comment can be.
_HEADER_SCAN_BYTES = 2048


def _header_pipeline(path: Path) -> "str | None":
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(_HEADER_SCAN_BYTES)
    except OSError:
        return None
    m = _HEADER_PIPELINE_RE.search(head)
    return m.group(1) if m else None


def prune_project_docs(conn: sqlite3.Connection, *, snapshot_db: Path,
                       workspace: Path, problem: str,
                       cutoff: str) -> dict:
    """Make `Problems/<project>/_docs/` match the cutoff. Returns one
    ledger row per area.

    This is the surface the 2026-09-04 replay paid for. The judge's
    `{papers_dir}` placeholder resolves to exactly this directory, and
    the rewind moved only the DB and `proofs/` — so row 1362, rewound to
    `12:37:16Z`, fired twice citing `tw_restoration_equivalence.md`,
    written 10.4 hours later (`criterion2_replay2_2026-09-04.md` §五.1).

    Four provenance signals, most authoritative first:

      1. `theory_documents.path` — the agent's landed documents. A row
         the rewind deleted takes its file; a surviving row keeps its
         file whatever the mtime says (a `copytree` rewrites mtimes,
         and the record does not).
      2. `problem_papers.paper_id` — a paper under `<area>/papers/<id>/`
         is bound to a problem by a row with a `created_at`. A paper
         still bound by some OTHER problem stays: that binding is not
         this rewind's to undo.
      3. the landing header's `pipeline:` id, for an agent document with
         no row (pre-v52, or a row the snapshot never had).
      4. git, else mtime — the only thing `_docs/user/` has. When
         NEITHER can date a file it is dropped and named in `undated`.
    """
    cut = _cutoff_dt(cutoff)
    ws = Path(workspace)
    from Tooling.state import project_docs as _project_docs
    from Tooling.state import projects as _projects
    project = (_projects.project_of(conn, problem)
               or problem.split(".", 1)[0])
    root = _project_docs.root(ws, project)

    snap = sqlite3.connect(f"file:{Path(snapshot_db).as_posix()}?mode=ro",
                           uri=True)
    snap.row_factory = sqlite3.Row

    def _col(c: sqlite3.Connection, sql: str) -> "set[str]":
        try:
            return {str(r[0]) for r in c.execute(sql) if r[0] is not None}
        except sqlite3.OperationalError:
            return set()

    doc_sql = "SELECT path FROM theory_documents WHERE path IS NOT NULL"
    paper_sql = "SELECT paper_id FROM problem_papers"
    pipe_sql = "SELECT id FROM pipelines"
    alive_docs, snap_docs = _col(conn, doc_sql), _col(snap, doc_sql)
    alive_papers, snap_papers = _col(conn, paper_sql), _col(snap, paper_sql)
    alive_pipes, snap_pipes = _col(conn, pipe_sql), _col(snap, pipe_sql)
    snap.close()

    rows: "dict[str, _Ledger]" = {}
    for area in _project_docs.AREAS:
        led = _Ledger(_rel(ws, root / area))
        rows[led.key] = led
        adir = root / area
        if not adir.is_dir():
            continue
        # Deepest-first so a paper directory emptied by its files can be
        # removed by the same walk that emptied it.
        for path in sorted(p for p in adir.rglob("*") if p.is_file()):
            rel = _rel(ws, path)
            # Relative to the AREA, not the workspace: `papers` is the
            # first component of a paper's address under an area, and
            # matching it anywhere in the absolute path would let a
            # project named `papers` claim every file in the tree.
            inner = path.relative_to(adir).as_posix().split("/")
            verdict, source = None, PROV_NONE
            if rel in alive_docs:
                verdict, source = True, "theory_documents"
            elif rel in snap_docs:
                verdict, source = False, "theory_documents"
            elif len(inner) > 1 and inner[0] == "papers":
                pid = inner[1]
                if pid in alive_papers:
                    verdict, source = True, "problem_papers"
                elif pid in snap_papers:
                    verdict, source = False, "problem_papers"
            if verdict is None:
                pipe = (_header_pipeline(path) if area == _project_docs.AREA_AGENT
                        else None)
                if pipe and pipe in alive_pipes:
                    verdict, source = True, "header"
                elif pipe and pipe in snap_pipes:
                    verdict, source = False, "header"
            if verdict is None:
                when, source = _file_provenance(ws, rel)
                verdict = when is not None and when <= cut
            if verdict:
                led.keep(source)
            else:
                led.drop(rel, source)
                _remove(path)
        # An emptied paper directory is not a document the judge can
        # read, but it IS a directory listing that says a paper is
        # there. Take the shells with the files.
        for d in sorted((p for p in adir.rglob("*") if p.is_dir()),
                        key=lambda p: len(p.parts), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                _remove(d)
    return {k: v.as_row() for k, v in rows.items()}


# ─── the run-scoped scratch ───
#
# `.drafts` / `.presearch` / `.groups` are id-keyed (the registry sweeps
# all three at reset for exactly that reason: an id means something else
# in the next workspace). An id the rewind deleted names a thing that did
# not exist at the cutoff — but a LIVE id is not enough on its own:
# `.drafts/strategist_plan_g<group>.md` is a rewrite-by-contract note, so
# group 691's note survived its own id check into the 09-04 scratch
# carrying the 09-04 text (§五.1: the judge's Context showed 2305 chars
# where the era's note held 1660). Both checks, or the entry goes.

#: `strategist_plan_g<GROUP>.md` — the same `g` prefix as the goal-keyed
#: notes beside it, for a different id space (`carry.SCRATCH_DIRS` says
#: so too). Matched FIRST, or the goal rule would claim it.
_PLAN_NOTE_RE = re.compile(r"^strategist_plan_g(\d+)\.md$")
#: `<kind>_g<goal>.md` and the `<kind>_g<goal>_patch.lean` slot beside it.
_GOAL_NOTE_RE = re.compile(r"^[a-z_]+_g(\d+)(?:_[a-z]+)?\.(?:md|lean)$")
_PRESEARCH_GOAL_RE = re.compile(r"^g(\d+)\.md$")
#: `inject<decision>.md` — a mint has no goal yet, so the Inject
#: decision id is the only stable key (`_presearch.mint_presearch_path`).
_PRESEARCH_INJECT_RE = re.compile(r"^inject(\d+)\.md$")


def _alive_ids(conn: sqlite3.Connection, table: str, problem: str,
               ) -> "set[int]":
    try:
        return {int(r[0]) for r in conn.execute(
            f"SELECT id FROM {table} WHERE problem = ?", (problem,))}
    except sqlite3.OperationalError:
        return set()


def prune_run_scratch(conn: sqlite3.Connection, *, workspace: Path,
                      problem: str, cutoff: str) -> dict:
    """Make `.drafts/`, `.presearch/` and `.groups/` match the cutoff.

    An entry is kept only when BOTH hold: the id in its name still
    exists in the rewound DB, and the bytes on disk predate the cutoff.
    An entry with no id in its name (`.drafts/strategist_plan.md`,
    `classify_feedback.txt`) is decided on the date alone.

    `.groups/<id>/PROGRAMME.md` is exempt from the date half: it is a
    RENDER, re-derived from the rewound DB by `refresh_derived_files`
    immediately after this call, so dating it would be dating the
    renderer rather than the scene.
    """
    cut = _cutoff_dt(cutoff)
    ws = Path(workspace)
    pdir = db.problem_dir(ws, problem)
    goals = _alive_ids(conn, "goals", problem)
    groups_alive = _alive_ids(conn, "groups", problem)
    decisions = _alive_ids(conn, "strategist_decisions", problem)

    def _id_verdict(name: str, kind: str) -> "tuple[bool | None, str]":
        """(does the id still exist, which id space) — (None, '') when
        the name carries no id at all."""
        if kind == "drafts":
            m = _PLAN_NOTE_RE.match(name)
            if m:
                return int(m.group(1)) in groups_alive, "group_id"
            m = _GOAL_NOTE_RE.match(name)
            if m:
                return int(m.group(1)) in goals, "goal_id"
            return None, ""
        m = _PRESEARCH_GOAL_RE.match(name)
        if m:
            return int(m.group(1)) in goals, "goal_id"
        m = _PRESEARCH_INJECT_RE.match(name)
        if m:
            return int(m.group(1)) in decisions, "decision_id"
        return None, ""

    rows: "dict[str, _Ledger]" = {}

    for kind in ("drafts", "presearch"):
        d = pdir / f".{kind}"
        led = _Ledger(_rel(ws, d))
        rows[led.key] = led
        if not d.is_dir():
            continue
        # Every entry, not just the files: a directory nobody expected
        # in here is exactly the surface this whole function exists to
        # stop leaking, and one that goes unlisted is one nobody knows
        # to check.
        for path in sorted(d.iterdir()):
            rel = _rel(ws, path)
            alive, space = _id_verdict(path.name, kind)
            if alive is False:
                led.drop(rel, space)
                _remove(path)
                continue
            when, source = _file_provenance(ws, rel)
            source = f"{space}+{source}" if space else source
            if when is not None and when <= cut:
                led.keep(source)
            else:
                led.drop(rel, source)
                _remove(path)

    gdir = pdir / ".groups"
    led = _Ledger(_rel(ws, gdir))
    rows[led.key] = led
    if gdir.is_dir():
        for entry in sorted(gdir.iterdir()):
            rel = _rel(ws, entry)
            if entry.is_dir() and entry.name.isdigit():
                if int(entry.name) in groups_alive:
                    led.keep("group_id")
                else:
                    led.drop(rel, "group_id")
                    _remove(entry)
                continue
            when, source = _file_provenance(ws, rel)
            if when is not None and when <= cut:
                led.keep(source)
            else:
                led.drop(rel, source)
                _remove(entry)
    return {k: v.as_row() for k, v in rows.items()}


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
                          problem: str,
                          removed: "list[Path] | None" = None) -> "list[Path]":
    """Re-derive the rendered files the DB owns — `TREE.md` and every
    group's `PROGRAMME.md` — so the scratch workspace shows the rewound
    scene, not the snapshot's. Both sides' round companions are re-rendered
    from this DB every round and the agents grep them in place: the
    first experiment-3
    run (2026-08-30) was judged against a TREE that still listed the
    goal the proposal was about to mint.

    A render that has nothing to say DELETES its file. `programme.render`
    returns None when the group has no passed revision left — and before
    2026-09-04 that silently left the LIVE `PROGRAMME.md` in place, so a
    scratch rewound past a group's first pass showed a Programme that did
    not exist yet. Absent is a state the renderer must be able to express.
    `removed` is an optional sink for the ledger; the removal happens
    either way."""
    from Tooling.state import groups as _groups, programme, tree
    written: list[Path] = []
    t = tree.write(conn, workspace, problem)
    if t is not None:
        written.append(t)
    pdir = db.problem_dir(workspace, problem)
    if not pdir.exists():
        return written
    for row in conn.execute("SELECT id FROM groups WHERE problem = ?", (problem,)):
        out = programme.render(conn, problem, pdir, int(row["id"]))
        if out is not None:
            written.append(out)
    # Every place a Programme could be rendered, checked against what
    # this pass actually wrote. Derived from the same `group_dir` the
    # renderer uses, so a stale file cannot hide in a layout this
    # function does not know about.
    top = _groups.top_group(conn, problem)
    top_id = int(top["id"]) if top is not None else None
    candidates = {pdir / programme.PROGRAMME_BASENAME}
    for row in conn.execute("SELECT id FROM groups WHERE problem = ?", (problem,)):
        candidates.add(programme.group_dir(pdir, int(row["id"]), top_id)
                       / programme.PROGRAMME_BASENAME)
    gdir = pdir / ".groups"
    if gdir.is_dir():
        candidates |= {p / programme.PROGRAMME_BASENAME
                       for p in gdir.iterdir() if p.is_dir()}
    for path in sorted(candidates):
        if path in written or not path.exists():
            continue
        path.unlink()
        if removed is not None:
            removed.append(path)
    return written


#: Written into the scratch by `rewind_files`. A scratch read a week
#: later has to be able to answer "which surfaces were rewound, on what
#: signal, and what was dropped" without the run log.
LEDGER_BASENAME = "_rewind_ledger.json"


def rewind_files(conn: sqlite3.Connection, *, snapshot_db: Path,
                 workspace: Path, problem: str, cutoff: str) -> dict:
    """The whole file half of the rewind, in the one order that works,
    with a ledger row per directory.

    Order is load-bearing: `.groups/<id>/` is pruned by group id BEFORE
    the Programme renders run, so a group the rewind deleted takes its
    directory with it instead of having a fresh `PROGRAMME.md` written
    back into it."""
    ws = Path(workspace)
    ledger: dict = {
        "problem": problem,
        "cutoff": cutoff,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "directories": {},
        "regenerated": [],
        "removed_renders": [],
        "undated": [],
    }
    pdir = db.problem_dir(ws, problem)

    proofs = pdir / "proofs"
    dropped = prune_proof_files(conn, snapshot_db=snapshot_db, workspace=ws,
                                problem=problem, cutoff=cutoff)
    kept = len(list(proofs.rglob("*.lean"))) if proofs.is_dir() else 0
    ledger["directories"][_rel(ws, proofs)] = {
        "kept": kept, "dropped": len(dropped),
        # Both proof rules read the record; `prune_proof_files` says in
        # its own docstring that it never reads an mtime.
        "provenance": "db", "dropped_entries": sorted(dropped),
        "undated": []}

    ledger["directories"].update(prune_project_docs(
        conn, snapshot_db=snapshot_db, workspace=ws, problem=problem,
        cutoff=cutoff))
    ledger["directories"].update(prune_run_scratch(
        conn, workspace=ws, problem=problem, cutoff=cutoff))

    removed_renders: "list[Path]" = []
    written = refresh_derived_files(conn, workspace=ws, problem=problem,
                                    removed=removed_renders)
    ledger["regenerated"] = sorted(_rel(ws, p) for p in written)
    ledger["removed_renders"] = sorted(_rel(ws, p) for p in removed_renders)
    for row in ledger["directories"].values():
        ledger["undated"] += row.get("undated", [])
    ledger["undated"] = sorted(ledger["undated"])

    for key in sorted(ledger["directories"]):
        row = ledger["directories"][key]
        print(f"[timetravel] {key}: kept {row['kept']} / dropped "
              f"{row['dropped']} ({row['provenance']})", flush=True)
    print(f"[timetravel] re-derived {len(written)} rendered file(s), "
          f"removed {len(removed_renders)} stale one(s)", flush=True)
    if ledger["undated"]:
        print(f"[timetravel] {len(ledger['undated'])} file(s) had NO "
              f"provenance signal and were dropped — see "
              f"{LEDGER_BASENAME}", flush=True)
    (ws / LEDGER_BASENAME).write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ledger


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
    rewind_files(conn, snapshot_db=snap / "asterism.db", workspace=dst,
                 problem=a.problem, cutoff=a.cutoff)
    for k, v in (("goals", conn.execute("SELECT COUNT(*) FROM goals WHERE problem=?", (a.problem,)).fetchone()[0]),
                 ("max decision", conn.execute("SELECT MAX(id) FROM strategist_decisions WHERE problem=?", (a.problem,)).fetchone()[0]),
                 ("max rev row", conn.execute("SELECT MAX(id) FROM programme_revisions WHERE problem=?", (a.problem,)).fetchone()[0])):
        print(f"[timetravel] {k}: {v}")
    conn.close()
    print(f"[timetravel] scratch workspace ready: {dst}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
