"""state.report — the problem's human-readable Ingest report.

`Ingest` is the problem's only terminal (Phase 6), and until now it left
nothing a mathematician could read: the record was a `ingested_at` stamp,
a review snapshot of anchor closures, and a tree of Lean files. HID §1.2
makes the terminal carry a summary in prose — statement, the route as an
argument, which bricks carry it, what was refuted, what is left open —
and §3.4 gives it a column.

Same shape as `state/programme.py`, deliberately: `problems.ingest_report`
is the SoT and `REPORT.md` in the problem dir is a read-only RENDER, with
one writer (`record` / `render`, on the Ingest commit path). Spawns are
write-denied on the file (`llm/claude_cli.py`), reset sweeps it
(`state/satellites.py`), and nothing else writes it by hand — a report
edited in place is a page the next render discards and a human reads as
the record.

It is its own module rather than a section of `programme.py` because the
two answer different questions: the Programme is the argument under
adversarial review, the report is what came of the whole problem.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

REPORT_BASENAME = "REPORT.md"

_HEADER = (
    "<!-- rendered by state.report — DO NOT EDIT; SoT is\n"
    "     problems.ingest_report. Writes go through the Ingest commit\n"
    "     only. -->\n\n")


def record(conn: sqlite3.Connection, problem: str,
           report: "str | None") -> None:
    """Store the terminal's report on the problem, verbatim. Blank →
    NULL: an absent report is not a failure (the prompt asking for one is
    staged, not live), and a whitespace-only string would read as "the
    author wrote one". Nothing else is normalised — this is the author's
    document, and the render is where presentation happens."""
    conn.execute("UPDATE problems SET ingest_report = ? WHERE name = ?",
                 (str(report) if str(report or "").strip() else None,
                  problem))
    conn.commit()


def read(conn: sqlite3.Connection, problem: str) -> Optional[str]:
    """The stored report, or None (never written, or a pre-v48 row)."""
    try:
        row = conn.execute(
            "SELECT ingest_report FROM problems WHERE name = ?",
            (problem,)).fetchone()
    except sqlite3.OperationalError:      # pre-v48 schema
        return None
    return None if row is None or row[0] is None else str(row[0])


def render(conn: sqlite3.Connection, problem: str,
           problem_dir: Path) -> Optional[Path]:
    """Write `REPORT.md` from the stored report. Returns the path, or
    None when there is nothing to render — no report, no file, so the
    directory never carries a page nobody wrote."""
    body = read(conn, problem)
    if not body:
        return None
    problem_dir.mkdir(parents=True, exist_ok=True)
    path = problem_dir / REPORT_BASENAME
    path.write_text(_HEADER + body.rstrip("\n") + "\n", encoding="utf-8")
    return path
