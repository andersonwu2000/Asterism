"""pipeline.round_materials — the round-fresh record, written the same
way for both sides of the adversarial debate.

The judge's projection is rebuilt from the DB every round (`TREE.md`
rendered fresh, `CATALOG.md` / `BATCHES.md` / `ADJUDICATIONS.md`
regenerated); the author's companions were written once, when the wake
spawned, and never again. So a goal proved — or parked, or delegated —
while a 7-to-10-round debate ran was visible to the judge and invisible
to the author, and the judge then fired criterion 5 on "roadmap says
landed, TREE says open": a contradiction the packet itself created.
Four remedies LABELLED that asymmetry (07-29 the snapshot label, 08-01
the verbatim Context.md, 08-15 the label's precedence sentence, 08-31
the fresh TREE render) — none removed it, because the author was never
handed the newer bytes at all.

One refresher, called by both: `refresh` (re)writes the four
machine-generated files into a working directory. `since` renders what
the record recorded after a given instant, and `delta` is the author's
per-round pack built on it — what moved since the previous rebuttal,
so the four fresh files do not have to be re-read to find the one line
that changed. `Context.md` is NOT touched on either side — it is the
author's snapshot, the evidence a quotation is checked against, and
rewriting it mid-debate would make the judge's verbatim copy a moving
target.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import sqlite3
from pathlib import Path


#: Where a round records the instant its rebuttal was issued. A file
#: in the attempts dir because the wake's rounds are separate spawns
#: against one directory — there is no in-memory round object that
#: survives them.
SINCE_MARK = "_since_mark.txt"

#: The delta pack's heading: round 1 measures from the author's
#: snapshot, every later round from the previous rebuttal.
SINCE_WAKE_BEGAN = "Since this wake began:"
SINCE_LAST_REBUTTAL = "Since the last rebuttal:"

#: What `refresh` writes. `ADJUDICATIONS.md` and `BATCHES.md` are
#: written only when their generators have something to say (no park
#: rulings / no batches → no file), so this names the roster, not a
#: guarantee that all four exist.
ROUND_FILES = ("TREE.md", "CATALOG.md", "BATCHES.md", "ADJUDICATIONS.md")


def refresh(conn: sqlite3.Connection, *, workspace: Path, problem: str,
            group_id: "int | None", target_dir: Path) -> list[str]:
    """(Re)write the round-fresh record files into `target_dir`.

    Returns the batch-outcome render that falls out of writing
    `BATCHES.md` — the judge welds it into its `PROGRAMME.md`; the
    author's side has no use for it.

    `workspace` is passed explicitly, never derived from `target_dir`:
    the judge's dir is a projection three levels down, and deriving the
    root from it made the catalog's signature read fall back to the
    bare DB statement on a domain-nested problem (cube_e2e 07-29).
    """
    from ..agent.context import (write_adjudications_companion,
                                 write_catalog_companion)
    from ..agent.phase2_context import _section_inject_batch_outcomes
    from ..state import db as _db, tree as _tree
    target_dir.mkdir(parents=True, exist_ok=True)
    # Rendered from THIS connection, not copied from the problem dir
    # (2026-08-31, 131 fleet reports: the dispatcher's copy could
    # describe another moment than the round reading it). Fallback to
    # the on-disk copy only if the render itself fails.
    try:
        (target_dir / "TREE.md").write_text(_tree.render(conn, problem),
                                            encoding="utf-8")
    except Exception:  # noqa: BLE001 — degrade to the dispatcher's copy
        src = _db.problem_dir(workspace, problem) / "TREE.md"
        if src.exists():
            shutil.copyfile(src, target_dir / "TREE.md")
    write_catalog_companion(conn, problem, target_dir,
                            workspace=workspace)
    write_adjudications_companion(conn, problem, target_dir)
    # Writes `BATCHES.md` (and any `PROGRAMME_G<id>.md`) as it renders.
    return _section_inject_batch_outcomes(
        conn, problem, workspace=workspace, group_id=group_id,
        attempts_dir=target_dir)


def snapshot_taken(ctx_path: Path) -> "_dt.datetime | None":
    """When the author's `Context.md` snapshot was taken, in UTC.

    One helper for both consumers: the judge prints it as the age of
    the file it is reading, and both sides ask `since` for what the
    record has done in the meantime. `None` when there is no snapshot
    (a wake whose Context was never written) — then there is no
    "since", either.
    """
    try:
        return _dt.datetime.fromtimestamp(ctx_path.stat().st_mtime,
                                          tz=_dt.timezone.utc)
    except OSError:
        return None


def _rows(conn: sqlite3.Connection, sql: str, args: tuple) -> list:
    """Query tolerant of a column an old DB has not migrated to yet
    (`actor` is v48, `programme_revisions.group_id` v35): the delta pack
    is an ADDITION to a rebuttal that must still be issued."""
    try:
        return list(conn.execute(sql, args))
    except sqlite3.OperationalError:
        return []


def since(conn: sqlite3.Connection, *, problem: str,
          since_iso: str) -> list[str]:
    """What the record recorded after `since_iso`, oldest first.

    Three structured sources, no free text: goal status transitions
    (`goal_events`), Programme revisions passed in any group of the
    problem, and strategist decisions that landed. Empty when nothing
    changed — the caller renders nothing at all in that case rather
    than a "nothing happened" line, which is noise on every round of
    every short debate.
    """
    out: "list[tuple[str, str]]" = []
    for r in _rows(
            conn,
            "SELECT e.at, e.goal_id, e.from_status, e.to_status, g.slug"
            " FROM goal_events e LEFT JOIN goals g ON g.id = e.goal_id"
            " WHERE e.problem = ? AND e.at > ? ORDER BY e.at, e.id",
            (problem, since_iso)):
        out.append((str(r["at"]),
                    f"g{r['goal_id']} {r['slug'] or '?'}: "
                    f"{r['from_status'] or '?'} → {r['to_status']}"))
    for r in _rows(
            conn,
            "SELECT created_at, rev, group_id FROM programme_revisions"
            " WHERE problem = ? AND status = 'passed' AND created_at > ?"
            " ORDER BY created_at, id",
            (problem, since_iso)):
        out.append((str(r["created_at"]),
                    f"grp{r['group_id']} rev {r['rev']} passed"))
    for r in _rows(
            conn,
            "SELECT created_at, decision_kind, target_id, actor"
            " FROM strategist_decisions"
            " WHERE problem = ? AND created_at > ?"
            " ORDER BY created_at, id",
            (problem, since_iso)):
        line = str(r["decision_kind"])
        if r["target_id"] is not None:
            line += f" on g{int(r['target_id'])}"
        # v48 §3.2 — a person's decision is named as the person's; a
        # peer group's number would read as one more group's opinion.
        if str(r["actor"] or "") == "human":
            line += " (human)"
        out.append((str(r["created_at"]), line))
    out.sort(key=lambda t: t[0])
    return [line for _, line in out]


def delta(conn: sqlite3.Connection, *, problem: str,
          attempts_dir: Path) -> "tuple[str, list[str]]":
    """This round's delta pack — `(heading, lines)`, empty list when the
    record stood still.

    PER ROUND, not cumulative (owner ruling 2026-09-03). Round 1
    measures from the author's `Context.md` snapshot: everything at or
    before it is already IN Context.md — the in-flight batches, the
    outcomes, the verdict this wake was queued with — and re-sending it
    would be the same fact twice in one packet. Every later round
    measures from where the last rebuttal was issued, so a 10-round
    debate carries each change exactly once.

    ADVANCES the mark: call it exactly once per rebuttal, as the
    rebuttal is issued.
    """
    from ..state import db as _db
    mark = attempts_dir / SINCE_MARK
    try:
        prior = mark.read_text(encoding="utf-8").strip()
    except OSError:
        prior = ""
    taken = snapshot_taken(attempts_dir / "Context.md")
    # `max` of two isoformat strings in the same shape: the snapshot is
    # the FLOOR even if a mark somehow predates it.
    since_iso = max(prior, taken.isoformat() if taken is not None else "")
    lines = (since(conn, problem=problem, since_iso=since_iso)
             if since_iso else [])
    try:
        mark.write_text(_db.now(), encoding="utf-8")
    except OSError:  # noqa: BLE001 — the rebuttal still goes out
        pass
    return (SINCE_LAST_REBUTTAL if prior else SINCE_WAKE_BEGAN), lines
