"""Read-side leaves with no call edge to the rest of the facade: the
review surface's statement-head display fallback (`_stmt_head`), the
spawn-usage telemetry rollup, a problem's paper bindings, and the
sandboxed raw problem-file read. They rode along at the end of the
retired Library-chapter module (split out of `data.py` 2026-08-28,
Phase B, B3) and moved here unchanged when the Library was retired.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ...state import db


def _stmt_head(text: str, start: int) -> str:
    """The declaration header from `start` to its top-level `:=` /
    `where` — the statement without the proof body. Bracket-depth walk,
    display fallback only (the oracle signature wins when stored)."""
    depth = 0
    i = start
    limit = min(len(text), start + 4000)
    while i < limit:
        ch = text[i]
        if ch in "([{⟨":
            depth += 1
        elif ch in ")]}⟩":
            depth -= 1
        elif depth == 0:
            if text.startswith(":=", i):
                return text[start:i].rstrip()
            if text.startswith("where", i) and (i == 0 or text[i - 1].isspace()):
                return text[start:i].rstrip()
            if text.startswith("\n\n", i):  # header can't span a blank line
                return text[start:i].rstrip()
        i += 1
    return text[start:limit].rstrip()


def telemetry_usage(conn: sqlite3.Connection, *,
                    since: "str | None" = None,
                    project: "str | None" = None) -> dict:
    """spawn_usage aggregation: totals per problem and per (problem,
    pipeline kind). `since` (an ISO timestamp, same format as the `ts`
    column) restricts the window — pass the running daemon's start time
    to get THIS run's burn instead of the all-time ledger. `project`
    scopes it to one shelf (the Engine Room lives inside a Project,
    §1.4) by the FK — `problems_of`, never the name's first segment,
    which stops being the Project the moment someone renames one."""
    per_problem: dict[str, dict] = {}
    where = " WHERE ts >= ?" if since else ""
    params: tuple = (since,) if since else ()
    for r in conn.execute(
            "SELECT COALESCE(problem, '') AS problem, kind,"
            " COUNT(*) AS spawns,"
            " SUM(input_tokens) AS in_tok, SUM(output_tokens) AS out_tok,"
            " SUM(cache_read_tokens) AS cache_tok,"
            " SUM(cache_new_tokens) AS cache_new,"
            " SUM(turns) AS turns, SUM(wall_sec) AS wall"
            " FROM spawn_usage" + where + " GROUP BY problem, kind",
            params):
        p = per_problem.setdefault(str(r["problem"]) or "(none)", {
            "problem": str(r["problem"]) or "(none)",
            "spawns": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_new_tokens": 0,
            "turns": 0, "wall_sec": 0.0,
            "kinds": [],
        })
        row = {
            "kind": str(r["kind"]),
            "spawns": int(r["spawns"]),
            "input_tokens": int(r["in_tok"] or 0),
            "output_tokens": int(r["out_tok"] or 0),
            "cache_read_tokens": int(r["cache_tok"] or 0),
            "cache_new_tokens": int(r["cache_new"] or 0),
            "turns": int(r["turns"] or 0),
            "wall_sec": float(r["wall"] or 0.0),
        }
        p["kinds"].append(row)
        p["spawns"] += row["spawns"]
        p["input_tokens"] += row["input_tokens"]
        p["output_tokens"] += row["output_tokens"]
        p["cache_read_tokens"] += row["cache_read_tokens"]
        p["cache_new_tokens"] += row["cache_new_tokens"]
        p["turns"] += row["turns"]
        p["wall_sec"] += row["wall_sec"]
    rows = sorted(per_problem.values(),
                  key=lambda x: -(x["input_tokens"] + x["output_tokens"]))
    if project is not None:
        from ...state import projects as _projects
        shelf = _projects.problems_of(conn, project)
        rows = [r for r in rows if r["problem"] in shelf]
    return {"problems": rows}


def problem_papers_detail(conn: sqlite3.Connection, workspace: Path,
                          problem: str) -> dict:
    """One problem's citations: bindings joined with shelf meta (a
    binding whose shelf slot vanished still shows, flagged missing).

    `path` is the paper's address in the Project's documents (§3.9), so
    a row can link straight to what it cites; None when the slot is
    missing, which is the same fact `missing` reports."""
    from ...papers import shelf as _shelf
    from ...state import project_docs as _project_docs
    from ...state import projects as _projects
    project = _projects.project_of(conn, problem) \
        or problem.split(".", 1)[0]
    out = []
    for r in db.paper_bindings(conn, problem):
        pid = str(r["paper_id"])
        pdir = _shelf.paper_dir(workspace, pid, project=project)
        meta = _shelf.load_meta(workspace, pid, project=project)
        out.append({
            "id": pid,
            "origin": str(r["origin"]),
            "reason": r["reason"],
            "source_name": meta.source_name if meta else None,
            "path": None if pdir is None else pdir.relative_to(
                _project_docs.root(workspace, project)).as_posix(),
            "missing": meta is None,
        })
    return {"problem": problem, "papers": out}


def read_problem_file(workspace: Path, problem: str,
                      rel_path: str) -> str | None:
    """Read-only file fetch, sandboxed to the problem directory.
    Only .lean / .md files; traversal outside the dir is refused."""
    if not rel_path.endswith((".lean", ".md")):
        return None
    pdir = db.problem_dir(workspace, problem).resolve()
    target = (pdir / rel_path).resolve()
    if not str(target).startswith(str(pdir)):
        return None
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return None
