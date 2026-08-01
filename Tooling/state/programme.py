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
`## Proof`, `## Roadmap` in that order (2026-07-23, user call: Thesis
renamed Proof — the section IS the root claim's proof, judged as one —
and moved before Roadmap, whose entries cash its gaps).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from .db import now

PROGRAMME_BASENAME = "PROGRAMME.md"

# Prominent-warning thresholds (design §2 + 07-29 bloat ruling): warn
# loudly, never hard-block. The Proof is the load-bearing mathematics
# and keeps the most headroom (healthy-heavy b6_1: 13 passed revs, max
# Proof 7.2k — never tripped). The observed bloat surfaces are the
# Argument (healthy ≤1.6k pre-endgame; verdict-war drafts 4-7k) and the
# package total (healthy max 21.2k passed; the pathological draft was
# 31.6k). Absolute thresholds by design: attention cost is absolute,
# and ratio triggers misfire on legitimate pivots (b6_1 rev 9→10 was a
# healthy 4.8×).
PROOF_WARN_CHARS = 10_000
ARGUMENT_WARN_CHARS = 3_000
DOC_WARN_CHARS = 25_000

_SECTION_ORDER = ("## Argument", "## Proof", "## Roadmap")


# ---------------------------------------------------------------------
# Proposal parsing / validation
# ---------------------------------------------------------------------

def parse_proposal(body: str) -> tuple[Optional[dict[str, str]], Optional[str]]:
    """Validate a proposal body against the four-section contract.

    Returns (sections, None) on success — sections maps
    {'title', 'argument', 'proof', 'roadmap'} to their text — or
    (None, teaching_error) on a contract violation.
    """
    if not isinstance(body, str) or not body.strip():
        return None, ("programme proposal is empty; deliver the four "
                      "sections: `# <Title>`, `## Argument`, "
                      "`## Proof`, `## Roadmap`")
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
                              "Argument/Proof/Roadmap appears exactly once")
            positions[stripped] = idx
    missing = [h for h in _SECTION_ORDER if h not in positions]
    if missing:
        return None, ("programme proposal is missing section(s): "
                      + ", ".join(f"`{h}`" for h in missing))
    idxs = [positions[h] for h in _SECTION_ORDER]
    if idxs != sorted(idxs):
        return None, ("programme sections out of order; required order is "
                      "`## Argument`, `## Proof`, `## Roadmap`")

    bounds = idxs + [len(lines)]
    sections = {"title": title}
    for name, start, end in zip(("argument", "proof", "roadmap"),
                                bounds[:-1], bounds[1:]):
        text = "\n".join(lines[start + 1:end]).strip()
        if not text:
            header = _SECTION_ORDER[("argument", "proof",
                                     "roadmap").index(name)]
            return None, f"programme `{header}` section is empty"
        sections[name] = text
    return sections, None


def length_warning(sections: dict[str, str],
                   body: "str | None" = None) -> Optional[str]:
    """Prominent over-length warnings (never a block); one line per
    tripped surface, joined. Shown to the judge (projection) and, on a
    rebuttal, echoed to the strategist with a shrink instruction."""
    warns = []
    n = len(sections.get("proof", ""))
    if n > PROOF_WARN_CHARS:
        warns.append(
            f"⚠ PROOF LENGTH WARNING: {n} chars (threshold "
            f"{PROOF_WARN_CHARS}). The Proof must stay readable — an "
            "unreadable Proof is itself rebuttable. Condense: "
            "superseded branches belong in Roadmap closure entries, "
            "not the Proof.")
    a = len(sections.get("argument", ""))
    if a > ARGUMENT_WARN_CHARS:
        warns.append(
            f"⚠ ARGUMENT LENGTH WARNING: {a} chars (threshold "
            f"{ARGUMENT_WARN_CHARS}). The Argument says why THIS batch "
            "— one screen. Cut narrative; mathematics belongs in the "
            "Proof, the route in the Roadmap.")
    d = len(body) if body is not None else sum(
        len(v) for v in sections.values())
    if d > DOC_WARN_CHARS:
        warns.append(
            f"⚠ PROPOSAL LENGTH WARNING: {d} chars total (threshold "
            f"{DOC_WARN_CHARS}). Distill the settled — a closed line "
            "collapses to its conclusion.")
    return "\n".join(warns) if warns else None


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


#: Nearest authorising ancestor, self first. The goal tree has no
#: parent column — an edge is `strategies.goal_id → strategy_subgoals
#: → subgoal_id` — so walking up is a recursive join over the link
#: table (`idx_ssg_subgoal` covers the step).
_AUTHORISING_REV_SQL = """
WITH RECURSIVE up(gid, depth) AS (
  VALUES(?, 0)
  UNION
  SELECT s.goal_id, up.depth + 1
    FROM strategy_subgoals ss
    JOIN strategies s ON s.id = ss.strategy_id
    JOIN up ON ss.subgoal_id = up.gid
)
SELECT pr.* FROM up
  JOIN strategist_decisions d
    ON CAST(d.produced_goal_id AS INTEGER) = up.gid
  JOIN programme_revisions pr
    ON pr.batch_id = d.batch_id AND pr.problem = ?
 WHERE pr.status = 'passed'
 ORDER BY up.depth ASC, d.id DESC
 LIMIT 1
"""


def rev_for_goal(conn: sqlite3.Connection, problem: str, *,
                 goal_id: "int | None" = None,
                 decision_id: "int | None" = None
                 ) -> Optional[sqlite3.Row]:
    """The revision whose `## Proof` AUTHORISED this piece of work.

    A worker must be shown the argument its goal was dispatched under,
    not whatever the Programme has become since. The two diverge
    routinely: a sibling branch triggers `pending_strategist_review`,
    the Strategist ships a new rev, and meanwhile this branch's
    sub-goals keep being auto-dispatched by the dispatcher without any
    Strategist wake. Reading the CURRENT rev then produces either a
    spurious `no_nl_correspondence` decline (the step is gone) or —
    worse, because nothing reports it — a silent re-anchoring onto a
    DIFFERENT step that happens to look apt.

    It also restores the batch-closure law (#118) over time. That law
    certifies "every claim this batch dispatches is fully argued in
    THIS batch's Proof", which the Adversary checks once, at dispatch.
    The tree it authorises outlives the check, so a mutable
    problem-scoped Proof silently voids the guarantee for every node
    already in flight. Pinning makes the certified pairing durable.

    Consequence worth stating: retracting a step no longer stops the
    work riding on it. That is correct — killing work is
    `ConfirmShelve`'s job, an explicit decision the Adversary sees, not
    a side effect of editing a document.

    Resolution, most specific first:
      1. `decision_id` — the batch that dispatched THIS spawn;
      2. the nearest ancestor (self included) with a producing decision
         — covers sub-goals the worker created, which have no decision
         of their own but inherit their parent's authorisation;
      3. `current_rev` — nothing above has one (fresh problem, or work
         that predates the Programme).
    """
    if decision_id is not None:
        row = conn.execute(
            "SELECT pr.* FROM strategist_decisions d"
            " JOIN programme_revisions pr"
            "   ON pr.batch_id = d.batch_id AND pr.problem = ?"
            " WHERE d.id = ? AND pr.status = 'passed'",
            (problem, decision_id)).fetchone()
        if row is not None:
            return row
    if goal_id is not None:
        row = conn.execute(_AUTHORISING_REV_SQL,
                           (int(goal_id), problem)).fetchone()
        if row is not None:
            return row
    return current_rev(conn, problem)


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
                     rounds: int,
                     discard_reason: Optional[str] = None) -> None:
    """Keep a discarded proposal + full criticism for audit.

    `discard_reason` (v34) names WHICH channel dropped it — adversary
    refutation, verify rounds exhausted, revision spawn failure. Every
    discard path records a row: the next wake's plan note may assert a
    dispatch that never happened, and the reason is what stops it
    re-deriving blind (07-29 SG feedback ×2)."""
    conn.execute(
        "INSERT INTO programme_revisions"
        " (problem, rev, body, status, verdict, dialogue, rounds,"
        "  batch_id, created_at, discard_reason)"
        " VALUES (?,?,?,'rejected',NULL,?,?,NULL,?,?)",
        (problem, next_rev_number(conn, problem), body,
         json.dumps(dialogue, ensure_ascii=False), rounds, now(),
         discard_reason))


def rejection_notice(conn: sqlite3.Connection,
                     problem: str) -> Optional[str]:
    """One-line record for the next wake after a discard (design §3:
    the fresh session gets the fact, never the failed draft)."""
    row = conn.execute(
        "SELECT * FROM programme_revisions WHERE problem = ?"
        " ORDER BY id DESC LIMIT 1", (problem,)).fetchone()
    if row is None or row["status"] != "rejected":
        return None
    keys = row.keys()
    why = (row["discard_reason"] if "discard_reason" in keys else None)
    # NULL on pre-v34 rows: those only ever came from the Adversary.
    cause = why or "adversary rebuttal"
    return (f"Programme rev {row['rev']} did not commit — {cause} after "
            f"{row['rounds']} round(s) ({row['created_at'][:10]}). "
            f"Batch not dispatched; draft not shown.")


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
