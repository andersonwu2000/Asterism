"""Read-side aggregation for the serve API.

Every function here takes a read-only connection (`db.connect_readonly`)
and returns JSON-shaped dicts. Status semantics are NEVER derived here
when a state-layer predicate exists (charter §1-3): stalled =
`db.problems_stalled`, awaiting_human = `db.problem_has_awaiting_human`
(batched via one SQL pass), sign-off = `problems.ingest_signoff_pending`.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..state import db


# ---------------------------------------------------------------------
# Status chip — one derivation, shared by board and problem detail.
# Precedence: blocked-on-human first (red/yellow), then terminal states,
# then the structural stall signal, else proving.
# ---------------------------------------------------------------------

def _status_chip(*, awaiting: bool, signoff: bool, bridged: bool,
                 ingested: bool, stalled: bool) -> str:
    if awaiting:
        return "awaiting_human"
    if signoff:
        return "signoff_pending"
    if bridged:
        return "bridged"
    if ingested:
        return "ingested"
    if stalled:
        return "stalled"
    return "proving"


def _awaiting_set(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in conn.execute(
        "SELECT DISTINCT problem FROM strategist_decisions"
        " WHERE outcome = 'awaiting_human'")}


def board(conn: sqlite3.Connection) -> dict:
    """Campaign-board aggregation: one row per problem, batch queries
    (no per-problem N+1 except the shared stall predicate)."""
    problems = conn.execute(
        "SELECT name, created_at, ingest_signoff_pending, ingested_at,"
        " library_bridged_at FROM problems ORDER BY name").fetchall()

    goal_counts: dict[str, dict[str, int]] = {}
    for r in conn.execute(
            "SELECT problem, status, COUNT(*) AS n FROM goals"
            " GROUP BY problem, status"):
        goal_counts.setdefault(str(r["problem"]), {})[str(r["status"])] = \
            int(r["n"])

    inflight: dict[str, int] = {}
    for r in conn.execute(
            "SELECT problem, COUNT(*) AS n FROM queue"
            " WHERE owner_pid IS NOT NULL GROUP BY problem"):
        inflight[str(r["problem"])] = int(r["n"])
    queued: dict[str, int] = {}
    for r in conn.execute(
            "SELECT problem, COUNT(*) AS n FROM queue GROUP BY problem"):
        queued[str(r["problem"])] = int(r["n"])

    last_event: dict[str, str] = {}
    for r in conn.execute(
            "SELECT problem, MAX(updated_at) AS t FROM strategist_decisions"
            " GROUP BY problem"):
        if r["t"]:
            last_event[str(r["problem"])] = str(r["t"])
    for r in conn.execute(
            "SELECT problem, MAX(created_at) AS t FROM goals"
            " GROUP BY problem"):
        if r["t"] and str(r["t"]) > last_event.get(str(r["problem"]), ""):
            last_event[str(r["problem"])] = str(r["t"])

    awaiting = _awaiting_set(conn)
    stalled = set(db.problems_stalled(conn))

    rows = []
    for p in problems:
        name = str(p["name"])
        counts = goal_counts.get(name, {})
        chip = _status_chip(
            awaiting=name in awaiting,
            signoff=bool(p["ingest_signoff_pending"]),
            bridged=p["library_bridged_at"] is not None,
            ingested=p["ingested_at"] is not None,
            stalled=name in stalled,
        )
        # Presentation refinement: the engine's stall signal also covers
        # problems that were never launched (frozen root / zero goals,
        # e.g. a benchmark batch). Red "stalled" is an attention chip;
        # a problem with zero progress and nothing alive is just idle.
        progressed = any(counts.get(s, 0) for s in
                         ("open", "attempting", "proved", "shelved",
                          "pending_strategist_review"))
        if chip == "stalled" and not progressed:
            chip = "idle"
        rows.append({
            "name": name,
            "status": chip,
            "goals": {
                "open": counts.get("open", 0) + counts.get("attempting", 0),
                "proved": counts.get("proved", 0),
                "shelved": counts.get("shelved", 0)
                + counts.get("pending_shelve_confirm", 0),
                "total": sum(counts.values()),
            },
            "in_flight": inflight.get(name, 0),
            "queued": queued.get(name, 0),
            "last_event": last_event.get(name),
            "created_at": str(p["created_at"]),
        })
    return {"problems": rows}


def problem_detail(conn: sqlite3.Connection, workspace: Path,
                   problem: str) -> dict | None:
    """Full problem view: goal DAG (nodes + strategy edges), strategist
    decision timeline, proofs file list."""
    prow = conn.execute(
        "SELECT name, created_at, ingest_signoff_pending, ingested_at,"
        " library_bridged_at, strategist_directive, last_strategist_at"
        " FROM problems WHERE name = ?", (problem,)).fetchone()
    if prow is None:
        return None

    dead_counts: dict[int, int] = {}
    for r in conn.execute(
            "SELECT target_id, COUNT(*) AS n FROM dead_attempts"
            " WHERE target_kind = 'Goal' GROUP BY target_id"):
        dead_counts[int(r["target_id"])] = int(r["n"])

    goals = []
    for g in conn.execute(
            "SELECT id, slug, status, kind, origin, depth, detached,"
            " attempts, alias_target_id, is_deliverable, statement,"
            " lean_path, created_at FROM goals WHERE problem = ?"
            " ORDER BY id", (problem,)):
        goals.append({
            "id": int(g["id"]),
            "slug": str(g["slug"]),
            "status": str(g["status"]),
            "kind": str(g["kind"]),
            "origin": str(g["origin"]),
            "depth": int(g["depth"]),
            "detached": bool(g["detached"]),
            "alias_target_id": g["alias_target_id"],
            "is_deliverable": bool(g["is_deliverable"]),
            "statement": str(g["statement"]),
            "lean_path": str(g["lean_path"]),
            "created_at": str(g["created_at"]),
            "attempts": int(g["attempts"]),
            "dead_attempts": dead_counts.get(int(g["id"]), 0),
        })

    goal_ids = {g["id"] for g in goals}
    strategies = []
    for s in conn.execute(
            "SELECT id, goal_id, status, created_by, created_at"
            " FROM strategies ORDER BY id"):
        if int(s["goal_id"]) in goal_ids:
            strategies.append({
                "id": int(s["id"]),
                "goal_id": int(s["goal_id"]),
                "status": str(s["status"]),
                "created_by": str(s["created_by"]),
                "created_at": str(s["created_at"]),
            })
    strat_ids = {s["id"] for s in strategies}
    edges = []
    for e in conn.execute(
            "SELECT strategy_id, subgoal_id, position FROM strategy_subgoals"
            " ORDER BY strategy_id, position"):
        if int(e["strategy_id"]) in strat_ids:
            edges.append({
                "strategy_id": int(e["strategy_id"]),
                "subgoal_id": int(e["subgoal_id"]),
                "position": int(e["position"]),
            })

    decisions = []
    for d in conn.execute(
            "SELECT id, batch_id, trigger_kind, decision_kind, target_id,"
            " brief, reason, payload, outcome, outcome_detail,"
            " produced_goal_id, produced_strategy_id, created_at, updated_at"
            " FROM strategist_decisions WHERE problem = ?"
            " ORDER BY id DESC LIMIT 200", (problem,)):
        try:
            payload = json.loads(d["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        decisions.append({
            "id": int(d["id"]),
            "batch_id": d["batch_id"],
            "trigger_kind": str(d["trigger_kind"]),
            "decision_kind": str(d["decision_kind"]),
            "target_id": d["target_id"],
            "brief": d["brief"],
            "reason": d["reason"],
            "payload": payload,
            "outcome": d["outcome"],
            "outcome_detail": d["outcome_detail"],
            "produced_goal_id": d["produced_goal_id"],
            "produced_strategy_id": d["produced_strategy_id"],
            "created_at": str(d["created_at"]),
            "updated_at": str(d["updated_at"]),
        })

    proofs_dir = db.problem_dir(workspace, problem) / "proofs"
    proof_files = sorted(
        f.name for f in proofs_dir.glob("*.lean")) if proofs_dir.is_dir() \
        else []

    awaiting = db.problem_has_awaiting_human(conn, problem)
    stalled = db.is_problem_stalled(conn, problem)
    return {
        "name": str(prow["name"]),
        "status": _status_chip(
            awaiting=awaiting,
            signoff=bool(prow["ingest_signoff_pending"]),
            bridged=prow["library_bridged_at"] is not None,
            ingested=prow["ingested_at"] is not None,
            stalled=stalled,
        ),
        "created_at": str(prow["created_at"]),
        "ingested_at": prow["ingested_at"],
        "library_bridged_at": prow["library_bridged_at"],
        "strategist_directive": prow["strategist_directive"],
        "goals": goals,
        "strategies": strategies,
        "strategy_edges": edges,
        "decisions": decisions,
        "proof_files": proof_files,
    }


def goal_detail(conn: sqlite3.Connection, problem: str,
                goal_id: int) -> dict | None:
    """Goal drill-down: full row + dead-attempt forensics (most recent
    first, capped)."""
    g = conn.execute(
        "SELECT * FROM goals WHERE id = ? AND problem = ?",
        (goal_id, problem)).fetchone()
    if g is None:
        return None
    dead = []
    for r in conn.execute(
            "SELECT id, pipeline_id, failure_reason, failure_detail,"
            " proposal_md, ts FROM dead_attempts"
            " WHERE target_kind = 'Goal' AND target_id = ?"
            " ORDER BY id DESC LIMIT 50", (goal_id,)):
        dead.append({
            "id": int(r["id"]),
            "pipeline_id": str(r["pipeline_id"]),
            "failure_reason": str(r["failure_reason"]),
            "failure_detail": r["failure_detail"],
            "proposal_md": r["proposal_md"],
            "ts": str(r["ts"]),
        })
    return {
        "id": int(g["id"]),
        "slug": str(g["slug"]),
        "status": str(g["status"]),
        "kind": str(g["kind"]),
        "origin": str(g["origin"]),
        "statement": str(g["statement"]),
        "lean_path": str(g["lean_path"]),
        "depth": int(g["depth"]),
        "detached": bool(g["detached"]),
        "alias_target_id": g["alias_target_id"],
        "is_deliverable": bool(g["is_deliverable"]),
        "created_at": str(g["created_at"]),
        "dead_attempts": dead,
    }


def inbox(conn: sqlite3.Connection, workspace: Path) -> dict:
    """Everything awaiting a human decision: unresolved amends (with the
    current on-disk file for the side-by-side diff) + paused ingest
    sign-offs (with snapshot summary)."""
    from ..state import amend as _amend
    amends = []
    for a in _amend.pending_amends(conn):
        current = ""
        fpath = db.problem_dir(workspace, a["problem"]) / a["file"]
        try:
            current = fpath.read_text(encoding="utf-8")
        except OSError:
            pass
        amends.append({**a, "current_body": current})

    signoffs = []
    for r in conn.execute(
            "SELECT name, ingested_at FROM problems"
            " WHERE ingest_signoff_pending = 1 ORDER BY name"):
        problem = str(r["name"])
        snap = None
        loaded = None
        try:
            from ..quality import review as _review
            loaded = _review.load_review_snapshot(conn, problem)
        except Exception:  # noqa: BLE001 — snapshot is best-effort
            loaded = None
        if loaded is not None:
            data, stored_at = loaded
            delivs = data.get("deliverables", [])
            snap = {
                "stored_at": stored_at,
                "deliverable_count": len(delivs),
                "ok_count": sum(1 for d in delivs if d.get("ok")),
            }
        signoffs.append({
            "problem": problem,
            "ingested_at": r["ingested_at"],
            "snapshot": snap,
        })
    return {"amends": amends, "signoffs": signoffs}


def inbox_count(conn: sqlite3.Connection) -> int:
    n = conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions"
        " WHERE decision_kind = 'RequestUserAmend'"
        "   AND outcome = 'awaiting_human'").fetchone()[0]
    m = conn.execute(
        "SELECT COUNT(*) FROM problems"
        " WHERE ingest_signoff_pending = 1").fetchone()[0]
    return int(n) + int(m)


def review(conn: sqlite3.Connection, problem: str) -> dict | None:
    """Ingest-time review snapshot (charter: GET never touches the
    gateway). None when the problem has no stored snapshot yet."""
    from ..quality import review as _review
    loaded = _review.load_review_snapshot(conn, problem)
    if loaded is None:
        return None
    data, stored_at = loaded
    return {"stored_at": stored_at, **data}


def library(conn: sqlite3.Connection) -> dict:
    """Bridged Library decls, grouped per source problem."""
    out = []
    for problem, rows in db.bridged_library_index(conn).items():
        out.append({
            "problem": problem,
            "decls": [{
                "slug": str(r["slug"]),
                "name": r["target_name"],
                "file": r["target_file"],
                "signature": r["signature"],
                "decl_kind": r["decl_kind"],
                "lifecycle": str(r["lifecycle"]),
            } for r in rows],
        })
    return {"problems": out}


def telemetry_usage(conn: sqlite3.Connection) -> dict:
    """spawn_usage aggregation: totals per problem and per (problem,
    pipeline kind)."""
    per_problem: dict[str, dict] = {}
    for r in conn.execute(
            "SELECT COALESCE(problem, '') AS problem, kind,"
            " COUNT(*) AS spawns,"
            " SUM(input_tokens) AS in_tok, SUM(output_tokens) AS out_tok,"
            " SUM(cache_read_tokens) AS cache_tok,"
            " SUM(turns) AS turns, SUM(wall_sec) AS wall"
            " FROM spawn_usage GROUP BY problem, kind"):
        p = per_problem.setdefault(str(r["problem"]) or "(none)", {
            "problem": str(r["problem"]) or "(none)",
            "spawns": 0, "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "turns": 0, "wall_sec": 0.0,
            "kinds": [],
        })
        row = {
            "kind": str(r["kind"]),
            "spawns": int(r["spawns"]),
            "input_tokens": int(r["in_tok"] or 0),
            "output_tokens": int(r["out_tok"] or 0),
            "cache_read_tokens": int(r["cache_tok"] or 0),
            "turns": int(r["turns"] or 0),
            "wall_sec": float(r["wall"] or 0.0),
        }
        p["kinds"].append(row)
        p["spawns"] += row["spawns"]
        p["input_tokens"] += row["input_tokens"]
        p["output_tokens"] += row["output_tokens"]
        p["cache_read_tokens"] += row["cache_read_tokens"]
        p["turns"] += row["turns"]
        p["wall_sec"] += row["wall_sec"]
    rows = sorted(per_problem.values(),
                  key=lambda x: -(x["input_tokens"] + x["output_tokens"]))
    return {"problems": rows}


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
