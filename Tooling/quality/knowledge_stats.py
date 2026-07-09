"""Offline knowledge-layer ROI telemetry — READ-ONLY.

Answers "does the money spent producing knowledge come back?" from
artifacts that already exist (no daemon-path hooks, retroactive over
past runs):

  * presearch hit-rate — a goal's cached `.presearch/g<gid>.md`
    candidates vs the landed proof text: how many injected candidate
    lemmas actually appear in the proof that closed the goal.
  * hint-probe win rate — Builder `proved` pipelines with NO
    spawn_usage row spent zero LLM quota (the free Mathlib `hint`
    probe closed the goal before any spawn; usage rows exist since
    schema v21).
  * lesson mention rate — KB lesson `[id-N]` cues / title substrings
    appearing in strategy proposal_md. WEAK PROXY (advice shapes
    thinking without being quoted); reported with that caveat.

Usage:  python -m Tooling.quality.knowledge_stats [--problem LIKE]
        asterism knowledge-stats [--problem LIKE]
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ..state import db
from ..state.assemble import strip_comments

_CAND_RE = re.compile(r"^- `([^`]+)`", re.MULTILINE)
_PRESEARCH_GID_RE = re.compile(r"^g(\d+)\.md$")


def _proof_text(workspace: Path, goal: sqlite3.Row) -> str | None:
    p = workspace / str(goal["lean_path"])
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def presearch_stats(conn: sqlite3.Connection, workspace: Path, *,
                    problem_like: str | None = None) -> dict:
    """Scan every cached presearch section; for PROVED goals, count
    which candidates appear (whole token, comments stripped) in the
    landed file."""
    rows: list[dict] = []
    like = problem_like or "%"
    problems = [str(r["name"]) for r in conn.execute(
        "SELECT name FROM problems WHERE name LIKE ?", (like,))]
    for prob in problems:
        pdir = db.problem_dir(workspace, prob) / ".presearch"
        if not pdir.is_dir():
            continue
        for f in sorted(pdir.glob("g*.md")):
            m = _PRESEARCH_GID_RE.match(f.name)
            if m is None:
                continue
            gid = int(m.group(1))
            goal = db.get_goal(conn, gid)
            if goal is None or str(goal["problem"]) != prob:
                continue
            try:
                cands = _CAND_RE.findall(f.read_text(encoding="utf-8"))
            except OSError:
                continue
            rec = {"problem": prob, "goal_id": gid,
                   "status": str(goal["status"]),
                   "n_candidates": len(cands), "used": []}
            if rec["status"] == "proved" and cands:
                text = _proof_text(workspace, goal)
                if text is not None:
                    body = strip_comments(text)
                    rec["used"] = [
                        c for c in cands
                        # match on the name's last component too — proofs
                        # cite `sub_le_iff_le_add` where presearch offered
                        # `tsub_le_iff_right`-style full names with prefix
                        if re.search(rf"\b{re.escape(c)}\b", body)
                        or re.search(
                            rf"\b{re.escape(c.rsplit('.', 1)[-1])}\b", body)
                    ]
            rows.append(rec)
    proved = [r for r in rows if r["status"] == "proved"
              and r["n_candidates"] > 0]
    return {
        "goals_with_presearch": len(rows),
        "proved_with_candidates": len(proved),
        "candidates_injected_on_proved": sum(
            r["n_candidates"] for r in proved),
        "candidates_used": sum(len(r["used"]) for r in proved),
        "proved_goals_using_any": sum(1 for r in proved if r["used"]),
        "rows": rows,
    }


def hint_stats(conn: sqlite3.Connection, *,
               problem_like: str | None = None) -> dict:
    """Builder `proved` pipelines split by whether a spawn_usage row
    exists: absent = the free `hint` probe won pre-spawn. Usage rows
    only exist since schema v21 — SELF-CALIBRATE the window to the
    earliest recorded usage row, else pre-v21 LLM wins masquerade as
    free hint wins."""
    like = problem_like or "%"
    since = conn.execute("SELECT MIN(ts) FROM spawn_usage").fetchone()[0]
    if since is None:
        return {"builder_proved": 0, "llm_spawned": 0,
                "hint_probe_wins": 0, "since": None}
    total = conn.execute(
        "SELECT COUNT(*) FROM pipelines p JOIN goals g"
        "  ON g.id = CAST(p.target_id AS INTEGER)"
        " WHERE p.kind='Builder' AND p.outcome='proved'"
        "   AND p.target_kind='Goal' AND g.problem LIKE ?"
        "   AND p.finished_at >= ?",
        (like, since)).fetchone()[0]
    with_spawn = conn.execute(
        "SELECT COUNT(DISTINCT p.id) FROM pipelines p"
        " JOIN goals g ON g.id = CAST(p.target_id AS INTEGER)"
        " JOIN spawn_usage u ON u.pipeline_id = p.id"
        " WHERE p.kind='Builder' AND p.outcome='proved'"
        "   AND p.target_kind='Goal' AND g.problem LIKE ?"
        "   AND p.finished_at >= ?",
        (like, since)).fetchone()[0]
    return {"builder_proved": int(total),
            "llm_spawned": int(with_spawn),
            "hint_probe_wins": int(total) - int(with_spawn),
            "since": str(since)}


def lesson_stats(conn: sqlite3.Connection, *,
                 problem_like: str | None = None) -> dict:
    """WEAK PROXY: lesson `[id-N]` cue / title-substring mentions in
    strategy proposal_md of the same problem."""
    like = problem_like or "%"
    lessons = conn.execute(
        "SELECT id, problem, title FROM kb_entries WHERE type='lesson'"
        " AND problem LIKE ?", (like,)).fetchall()
    mentioned = 0
    for les in lessons:
        cue = f"[id-{int(les['id'])}]"
        title = str(les["title"] or "").strip()
        hit = conn.execute(
            "SELECT 1 FROM strategies s JOIN goals g ON g.id = s.goal_id"
            " WHERE g.problem = ? AND (instr(s.proposal_md, ?) > 0"
            "   OR (length(?) > 11 AND instr(s.proposal_md, ?) > 0))"
            " LIMIT 1",
            (str(les["problem"]), cue, title, title)).fetchone()
        if hit is not None:
            mentioned += 1
    return {"lessons": len(lessons), "mentioned_in_proposals": mentioned}


def render(conn: sqlite3.Connection, workspace: Path, *,
           problem_like: str | None = None) -> str:
    ps = presearch_stats(conn, workspace, problem_like=problem_like)
    hs = hint_stats(conn, problem_like=problem_like)
    ls = lesson_stats(conn, problem_like=problem_like)
    lines = ["# knowledge-layer ROI (offline, read-only)", ""]
    lines.append(f"presearch: {ps['goals_with_presearch']} goals carry a "
                 f"cached section; {ps['proved_with_candidates']} proved "
                 f"with >=1 candidate")
    if ps["proved_with_candidates"]:
        lines.append(
            f"  candidates on proved goals: "
            f"{ps['candidates_injected_on_proved']} injected, "
            f"{ps['candidates_used']} appear in the landed proof "
            f"({ps['candidates_used']/max(1, ps['candidates_injected_on_proved']):.0%})")
        lines.append(
            f"  proved goals using >=1 candidate: "
            f"{ps['proved_goals_using_any']}/{ps['proved_with_candidates']}"
            f" ({ps['proved_goals_using_any']/max(1, ps['proved_with_candidates']):.0%})")
    lines.append(
        f"builder (since usage telemetry {str(hs.get('since'))[:10]}): "
        f"{hs['builder_proved']} proved — "
        f"{hs['hint_probe_wins']} by the FREE hint probe (no spawn), "
        f"{hs['llm_spawned']} by LLM"
        + (f" ({hs['hint_probe_wins']/max(1, hs['builder_proved']):.0%} free)"
           if hs["builder_proved"] else ""))
    lines.append(
        f"lessons (weak textual proxy): {ls['mentioned_in_proposals']}/"
        f"{ls['lessons']} ever mentioned in a strategy proposal")
    return "\n".join(lines)


def main(argv: "list[str] | None" = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--problem", default=None,
                    help="SQL LIKE filter, e.g. 'Putnam.%%'")
    ap.add_argument("--workspace", default=".")
    args = ap.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    conn = sqlite3.connect(
        f"file:{(workspace / 'asterism.db').as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    print(render(conn, workspace, problem_like=args.problem))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
