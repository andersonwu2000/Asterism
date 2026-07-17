"""state.programme — the Programme store (research mode).

The Programme is the adversarially-reviewed argument layer between the
Manifest and the bricks (research_mode_design.md §2). SoT is the
`programme_revisions` table (v30): `passed` rows form the revision
chain (the latest passed row IS the current Programme), `rejected`
rows keep a discarded proposal plus its criticism dialogue for audit.
`PROGRAMME.md` in the problem dir is a read-only render; spawns are
write-denied on it and the only writers are `record_pass` /
`record_rejection` on the strategist commit path.

Proposal body contract (four sections, prose discipline — no schema
beyond the headers): a `# <Title>` line, then `## Argument`,
`## Roadmap`, `## Thesis` in that order.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from .db import now

PROGRAMME_BASENAME = "PROGRAMME.md"

# Prominent-warning threshold for the Thesis section (design §2: the
# whole story must stay readable; warn loudly, never hard-block).
THESIS_WARN_CHARS = 10_000

_SECTION_ORDER = ("## Argument", "## Roadmap", "## Thesis")


# ---------------------------------------------------------------------
# Proposal parsing / validation
# ---------------------------------------------------------------------

def parse_proposal(body: str) -> tuple[Optional[dict[str, str]], Optional[str]]:
    """Validate a proposal body against the four-section contract.

    Returns (sections, None) on success — sections maps
    {'title', 'argument', 'roadmap', 'thesis'} to their text — or
    (None, teaching_error) on a contract violation.
    """
    if not isinstance(body, str) or not body.strip():
        return None, ("programme proposal is empty; deliver the four "
                      "sections: `# <Title>`, `## Argument`, "
                      "`## Roadmap`, `## Thesis`")
    lines = body.splitlines()
    first = next((ln for ln in lines if ln.strip()), "")
    if not (first.startswith("# ") and not first.startswith("## ")):
        return None, ("programme proposal must open with a `# <Title>` "
                      f"line (got {first[:60]!r}); the Title is this "
                      "batch's goal in one line")
    title = first[2:].strip()
    if not title:
        return None, "programme `# <Title>` line is empty"

    positions: dict[str, int] = {}
    for idx, ln in enumerate(lines):
        stripped = ln.rstrip()
        if stripped in _SECTION_ORDER:
            if stripped in positions:
                return None, (f"duplicate `{stripped}` section; each of "
                              "Argument/Roadmap/Thesis appears exactly once")
            positions[stripped] = idx
    missing = [h for h in _SECTION_ORDER if h not in positions]
    if missing:
        return None, ("programme proposal is missing section(s): "
                      + ", ".join(f"`{h}`" for h in missing))
    idxs = [positions[h] for h in _SECTION_ORDER]
    if idxs != sorted(idxs):
        return None, ("programme sections out of order; required order is "
                      "`## Argument`, `## Roadmap`, `## Thesis`")

    bounds = idxs + [len(lines)]
    sections = {"title": title}
    for name, start, end in zip(("argument", "roadmap", "thesis"),
                                bounds[:-1], bounds[1:]):
        text = "\n".join(lines[start + 1:end]).strip()
        if not text:
            header = _SECTION_ORDER[("argument", "roadmap",
                                     "thesis").index(name)]
            return None, f"programme `{header}` section is empty"
        sections[name] = text
    return sections, None


def thesis_warning(sections: dict[str, str]) -> Optional[str]:
    """Prominent over-length warning for the Thesis (never a block)."""
    n = len(sections.get("thesis", ""))
    if n <= THESIS_WARN_CHARS:
        return None
    return (f"⚠ THESIS LENGTH WARNING: {n} chars (threshold "
            f"{THESIS_WARN_CHARS}). The Thesis must stay a readable "
            "whole story — an unreadable Thesis is itself rebuttable. "
            "Condense: superseded branches belong in Roadmap closure "
            "entries, not the Thesis.")


# ---------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------

def current_rev(conn: sqlite3.Connection,
                problem: str) -> Optional[sqlite3.Row]:
    """The latest passed revision row, or None before bootstrap."""
    return conn.execute(
        "SELECT * FROM programme_revisions"
        " WHERE problem = ? AND status = 'passed'"
        " ORDER BY rev DESC LIMIT 1", (problem,)).fetchone()


def next_rev_number(conn: sqlite3.Connection, problem: str) -> int:
    row = current_rev(conn, problem)
    return (row["rev"] + 1) if row else 1


def record_pass(conn: sqlite3.Connection, problem: str, body: str,
                verdict: dict[str, Any],
                dialogue: list[dict[str, Any]],
                rounds: int, batch_id: Optional[str]) -> int:
    """Advance the revision chain. Returns the new rev number."""
    rev = next_rev_number(conn, problem)
    conn.execute(
        "INSERT INTO programme_revisions"
        " (problem, rev, body, status, verdict, dialogue, rounds,"
        "  batch_id, created_at)"
        " VALUES (?,?,?,'passed',?,?,?,?,?)",
        (problem, rev, body, json.dumps(verdict, ensure_ascii=False),
         json.dumps(dialogue, ensure_ascii=False), rounds, batch_id,
         now()))
    return rev


def record_rejection(conn: sqlite3.Connection, problem: str, body: str,
                     dialogue: list[dict[str, Any]],
                     rounds: int) -> None:
    """Keep a discarded proposal + full criticism for audit."""
    conn.execute(
        "INSERT INTO programme_revisions"
        " (problem, rev, body, status, verdict, dialogue, rounds,"
        "  batch_id, created_at)"
        " VALUES (?,?,?,'rejected',NULL,?,?,NULL,?)",
        (problem, next_rev_number(conn, problem), body,
         json.dumps(dialogue, ensure_ascii=False), rounds, now()))


def rejection_notice(conn: sqlite3.Connection,
                     problem: str) -> Optional[str]:
    """One-line record for the next wake after a discard (design §3:
    the fresh session gets the fact, never the failed draft)."""
    row = conn.execute(
        "SELECT * FROM programme_revisions WHERE problem = ?"
        " ORDER BY id DESC LIMIT 1", (problem,)).fetchone()
    if row is None or row["status"] != "rejected":
        return None
    return (f"Your previous proposal for Programme rev {row['rev']} was "
            f"rejected by the Adversary after {row['rounds']} round(s) "
            f"({row['created_at'][:10]}). Re-derive from scratch against "
            "the current Programme — the discarded draft is intentionally "
            "not shown.")


# ---------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------

def _verdict_summary(verdict_json: Optional[str]) -> str:
    if not verdict_json:
        return "(no verdict record)"
    try:
        v = json.loads(verdict_json)
    except (TypeError, ValueError):
        return "(unparseable verdict record)"
    reservations = v.get("reservations") or []
    if not reservations:
        return "passed with no reservations"
    lines = ["passed with reservations:"]
    lines += [f"  - {r}" for r in reservations]
    return "\n".join(lines)


def render(conn: sqlite3.Connection, problem: str,
           problem_dir: Path) -> Optional[Path]:
    """Write PROGRAMME.md (read-only render of the current rev).

    Header = rev N + last verdict summary; full history stays in the
    DB (design §2: no revision log in the render). Returns the path,
    or None before bootstrap (no passed rev → no file)."""
    row = current_rev(conn, problem)
    if row is None:
        return None
    path = problem_dir / PROGRAMME_BASENAME
    header = (
        "<!-- rendered by state.programme — DO NOT EDIT; SoT is the\n"
        "     programme_revisions table. Writes go through the passed\n"
        "     proposal commit only. -->\n"
        f"<!-- rev {row['rev']} · {row['created_at'][:19]} · "
        f"rounds {row['rounds']} -->\n"
        f"<!-- adversary: {_verdict_summary(row['verdict'])} -->\n\n")
    path.write_text(header + row["body"] + "\n", encoding="utf-8")
    return path
