"""Where a reviewed theory document lands, and the row that records
every run — accepted or not.

`Problems/<project>/_docs/agent/` is the Assistant's half of the
Project's shelf (HID §3.6), and the theory layer is the second writer
into it. Everything goes through `state/project_docs`, the module that
owns the three-check write fence — a caller that joins the strings
itself is a caller that writes `../../` into the tree.

A REJECTED run lands its document too (owner ruling 2026-09-06). It
used to write only the row, on the argument that the document had not
earned a place on the shelf — but the shelf is not a prize, it is the
programme's record, and what was tried on a wall and why it failed is
exactly the post-mortem material the next request is written against.
A record reachable only through a `dead_attempts` blob is a record
nobody reads.

WHAT THE STATUS DOES NOT DECIDE IS CITABILITY. The rubric's criterion 2
is Rigour, and the reviewer clears it by re-deriving the theorems — so
a document refused on 1/3/4 with criterion 2 clear carries RESULTS, and
one refused on criterion 2 carries attempts however well the rest of it
reads. The header says which, in one fixed spelling
(`verdict.RIGOUR_DEFECTIVE`), and so do the two other surfaces a citing
seat meets it on (`agent/context.py`'s Notes roster, the Strategist's
outcome detail).

THE ATTEMPTS DIR IS STILL NOT THE RECORD. `.attempts/<pid>/` is
ephemeral by design — "deleted at pipeline end (success or failure); DB
is single source of truth" (`state/db/core.py`, the `dead_attempts`
note) — and a dead Formalizer's evidence survives it because the worker
snapshots the dir into `dead_attempts.artifacts` BEFORE `WorkArea`
tears it down (`core/dispatcher/worker.py`). The Theorist's branch does
the same, so a wake that died before any ruling still has its
`report.md` in that column; MEASURED 2026-09-05 through `_run_pipeline`,
artifacts = `['report.md']` with the directory already gone. That road
lands nothing — nobody reviewed it — and `path` stays NULL for it.
"""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .verdict import (RIGOUR_DEFECTIVE, fired_criteria, rigour_is_defective,
                      verdict_lines as _verdict_lines)

#: Filename stem shape: `g<group>_<YYYYMMDD-HHMM>[_rejected]_<slug>`.
#: The group and the minute are what make two documents on one wall
#: tellable apart in a flat listing; the slug is what makes either of
#: them findable; the `rejected` segment is what stops a reader citing
#: the wrong one (owner addendum 2026-09-06). It rides BETWEEN the two
#: so the group/minute ordering is untouched and the slug still ends the
#: name — a document is found by its subject either way.
_STAMP_FMT = "%Y%m%d-%H%M"
_SLUG_MAX = 48

#: The two review outcomes, spelled the way `theory_documents.status`
#: spells them — the landed file's name and its header's first line are
#: both that column, on disk.
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"


def slug_for(body: str) -> str:
    """The document's own name for itself, as a filename slug.

    The `# ` title if the author wrote one — the line the writer put
    first IS the title, the same convention the notes roster reads —
    and otherwise the Abstract's first sentence, which is where this
    document's structure puts the claim. Neither is invented: a
    document with no title and no abstract gets `untitled`, and is
    still findable by its group and its minute."""
    title = ""
    for ln in body.splitlines():
        m = re.match(r"^#\s+(\S.*?)\s*$", ln)
        if m:
            title = m.group(1)
            break
    if not title:
        lines = body.splitlines()
        for i, ln in enumerate(lines):
            if re.match(r"^#{1,6}\s+abstract\b", ln.strip(), re.IGNORECASE):
                rest = " ".join(x.strip() for x in lines[i + 1:i + 12])
                first = re.split(r"(?<=[.!?])\s", rest.strip(), maxsplit=1)
                title = first[0] if first else ""
                break
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)[:_SLUG_MAX].strip("_")
    return slug or "untitled"


def document_name(*, group_id: "int | None", body: str,
                  when: "datetime | None" = None,
                  status: str = STATUS_ACCEPTED) -> str:
    when = when or datetime.now(timezone.utc)
    gid = "none" if group_id is None else str(int(group_id))
    mark = "_rejected" if status == STATUS_REJECTED else ""
    return (f"g{gid}_{when.strftime(_STAMP_FMT)}{mark}"
            f"_{slug_for(body)}.md")


def _free_name(base_dir: Path, name: str) -> str:
    """`name`, or the first `<stem>_2.md`, `<stem>_3.md`… nothing holds.

    None of the three parts of a document's name is unique: two wakes on
    one wall are asked the SAME objective and so write the same title,
    and `project_docs.write` overwrites without a word. That was
    survivable while only the accepted road landed — one document per
    wall, hours apart — and is not now that every run lands: the record
    the 2026-09-06 ruling exists to keep is exactly the one a same-minute
    twin would destroy, and both `theory_documents` rows would then point
    at one file.

    Same idiom as `verdict.keep_rejected_verdict`: never overwrite
    evidence, take the next free name."""
    stem = name[:-3] if name.endswith(".md") else name
    for i in range(1, 1000):
        candidate = name if i == 1 else f"{stem}_{i}.md"
        if not (base_dir / candidate).exists():
            return candidate
    return f"{stem}_{uuid.uuid4().hex[:8]}.md"


_ACCEPTED_PROSE = "Written by the theory layer and accepted by its reviewer."
#: A refused document names the ONE question a reader of it has: may I
#: cite this? The status does not answer it — criterion 2 does.
_REJECTED_PROSE = (
    "Written by the theory layer and REFUSED by its reviewer; landed as "
    "the record of what was tried and why it failed. Citability follows "
    "criterion 2 (Rigour) below, not this status.")


def header(*, group_id: "int | None", pipeline_id: str, rounds: int,
           verdict_lines: "list[str]", status: str = STATUS_ACCEPTED,
           fired: "list[str] | None" = None,
           rigour_defective: bool = False) -> str:
    """The provenance comment the landed file opens with.

    An HTML comment because the file is read as prose by the next
    author and as a document by a person, and neither should trip over
    framework bookkeeping — but it must be IN the file: the attempts dir
    it was reviewed in is deleted at pipeline end, so the reviewer's
    per-criterion sentence has nowhere else to survive. That sentence is
    the only durable statement of what was actually checked.

    `status:` OPENS it, on both roads. The shelf holds refused documents
    too now, and a reader who has to reach the fourth line to learn
    which kind this is has already started reading it as a result."""
    rejected = status == STATUS_REJECTED
    lines = ["<!--",
             f"status: {status}",
             _REJECTED_PROSE if rejected else _ACCEPTED_PROSE,
             f"group: {'(none)' if group_id is None else int(group_id)}",
             f"pipeline: {pipeline_id}",
             f"rounds: {int(rounds)}"]
    if fired:
        lines.append("criteria fired: " + ", ".join(str(k) for k in fired))
    if rigour_defective:
        # Only when it fired: the absence of this line is what says the
        # reviewer re-derived the theorems, and a `rigour: fine` twin
        # would make the flag one more line to read rather than one to
        # find.
        lines.append(RIGOUR_DEFECTIVE)
    lines += [f"{ln}" for ln in verdict_lines]
    lines.append("-->")
    return "\n".join(lines)


def land(workspace: Path, conn: sqlite3.Connection, *, problem: str,
         group_id: "int | None", pipeline_id: str, body: str,
         rounds: int, verdict: "dict | None",
         status: str = STATUS_ACCEPTED) -> str:
    """Write the reviewed document into the Project's shelf; returns its
    workspace-relative path.

    BOTH roads land (owner ruling 2026-09-06). Same shelf, same naming:
    a refused document is the record of what was tried on that wall, and
    the header is where a reader learns which kind it is holding."""
    from ...state import project_docs as _project_docs
    from ...state import projects as _projects
    project = (_projects.project_of(conn, problem)
               or problem.split(".", 1)[0])
    rejected = status == STATUS_REJECTED
    name = _free_name(
        _project_docs.root(Path(workspace), project)
        / _project_docs.AREA_AGENT,
        document_name(group_id=group_id, body=body, status=status))
    rel = _project_docs.write(
        workspace, project, f"agent/{name}",
        header(group_id=group_id, pipeline_id=pipeline_id, rounds=rounds,
               verdict_lines=_verdict_lines(verdict), status=status,
               fired=fired_criteria(verdict) if rejected else None,
               rigour_defective=rejected and rigour_is_defective(verdict))
        + "\n\n" + body.rstrip("\n") + "\n",
        area=_project_docs.AREA_AGENT)
    return (_project_docs.root(Path(workspace), project) / rel
            ).relative_to(Path(workspace)).as_posix()


def record(conn: sqlite3.Connection, *, problem: str,
           group_id: "int | None", pipeline_id: str,
           decision_id: "int | None", objective: str, situation: str,
           path: "str | None", status: str, rounds: int,
           verdict_json: "str | None") -> int:
    """The `theory_documents` row. Written for BOTH outcomes — see the
    module docstring."""
    from ...state.db import now as _now
    cur = conn.execute(
        "INSERT INTO theory_documents (problem, group_id, pipeline_id,"
        " decision_id, objective, situation, path, status, rounds,"
        " verdict_json, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (problem, None if group_id is None else int(group_id),
         pipeline_id, decision_id, objective, situation, path, status,
         int(rounds), verdict_json, _now()))
    conn.commit()
    return int(cur.lastrowid)
