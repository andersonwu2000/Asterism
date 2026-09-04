"""Where an accepted theory document lands, and the row that records
every run — accepted or not.

`Problems/<project>/_docs/agent/` is the Assistant's half of the
Project's shelf (HID §3.6), and the theory layer is the second writer
into it. Everything goes through `state/project_docs`, the module that
owns the three-check write fence — a caller that joins the strings
itself is a caller that writes `../../` into the tree.

A REJECTED run writes no document and a row all the same. The document
stays in the attempts dir, which is deleted at pipeline end, and that
is the point: it did not earn a place in the Project's shelf. What
survives is the request, the round count and the last verdict — the
evidence the next request on that same wall is written against.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

#: Filename stem shape: `g<group>_<YYYYMMDD-HHMM>_<slug>`. The group and
#: the minute are what make two documents on one wall tellable apart in
#: a flat listing; the slug is what makes either of them findable.
_STAMP_FMT = "%Y%m%d-%H%M"
_SLUG_MAX = 48


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
                  when: "datetime | None" = None) -> str:
    when = when or datetime.now(timezone.utc)
    gid = "none" if group_id is None else str(int(group_id))
    return f"g{gid}_{when.strftime(_STAMP_FMT)}_{slug_for(body)}.md"


def header(*, group_id: "int | None", pipeline_id: str, rounds: int,
           clear_lines: "list[str]") -> str:
    """The provenance comment the landed file opens with.

    An HTML comment because the file is read as prose by the next
    author and as a document by a person, and neither should trip over
    framework bookkeeping — but it must be IN the file: the attempts dir
    it was reviewed in is deleted at pipeline end, so the reviewer's
    per-criterion sentence has nowhere else to survive. That sentence is
    the only durable statement of what was actually checked."""
    lines = ["<!--",
             "Written by the theory layer and accepted by its reviewer.",
             f"group: {'(none)' if group_id is None else int(group_id)}",
             f"pipeline: {pipeline_id}",
             f"rounds: {int(rounds)}"]
    lines += [f"{ln}" for ln in clear_lines]
    lines.append("-->")
    return "\n".join(lines)


def land(workspace: Path, conn: sqlite3.Connection, *, problem: str,
         group_id: "int | None", pipeline_id: str, body: str,
         rounds: int, clear_lines: "list[str]") -> str:
    """Write the accepted document into the Project's shelf; returns its
    workspace-relative path."""
    from ...state import project_docs as _project_docs
    from ...state import projects as _projects
    project = (_projects.project_of(conn, problem)
               or problem.split(".", 1)[0])
    name = document_name(group_id=group_id, body=body)
    rel = _project_docs.write(
        workspace, project, f"agent/{name}",
        header(group_id=group_id, pipeline_id=pipeline_id, rounds=rounds,
               clear_lines=clear_lines) + "\n\n" + body.rstrip("\n") + "\n",
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
