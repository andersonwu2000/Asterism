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


def _live_daemon_pid(daemon: "dict | None") -> "int | None":
    if daemon and daemon.get("running") and daemon.get("pid"):
        return int(daemon["pid"])
    return None


def _working(conn: sqlite3.Connection, daemon: "dict | None",
             name: str) -> bool:
    """True iff a live daemon is actually on this problem (scope LIKE
    match; empty scope = workspace-wide run)."""
    if _live_daemon_pid(daemon) is None:
        return False
    scope = daemon.get("scope") if daemon else None
    if not scope:
        return True
    row = conn.execute("SELECT ? LIKE ?", (name, scope)).fetchone()
    return bool(row and row[0])


def _refine_chip(chip: str, *, working: bool, progressed: bool,
                 queued: int) -> str:
    """Presentation refinements shared by board() and problem_detail()
    — the two surfaces must agree.

    "proving" is an engine-liveness claim, not a DB-residue reading:
    without a live daemon scoped to this problem it degrades to
    "paused" (unfinished work remains) or "idle" (never launched).
    Within a live run, stalled+queued means the engine is between
    batches (the pending Strategist wake) — show proving, don't
    flicker red in the gap; a never-launched stalled problem (frozen
    root / zero goals) is idle, not stuck.
    """
    if chip == "stalled":
        if queued > 0:
            chip = "proving"
        elif not progressed:
            return "idle"
    if chip == "proving" and not working:
        return "paused" if progressed else "idle"
    return chip


def _awaiting_set(conn: sqlite3.Connection) -> set[str]:
    return {str(r[0]) for r in conn.execute(
        "SELECT DISTINCT problem FROM strategist_decisions"
        " WHERE outcome = 'awaiting_human'")}


def board(conn: sqlite3.Connection, *, daemon: "dict | None" = None) -> dict:
    """Campaign-board aggregation: one row per problem, batch queries
    (no per-problem N+1 except the shared stall predicate). `daemon` is
    the `daemon_status()` dict — status chips and in-flight counts are
    engine-liveness claims, so they must be gated on it (None = treat
    as not running)."""
    problems = conn.execute(
        "SELECT name, created_at, ingest_signoff_pending, ingested_at,"
        " library_bridged_at FROM problems ORDER BY name").fetchall()

    goal_counts: dict[str, dict[str, int]] = {}
    for r in conn.execute(
            "SELECT problem, status, COUNT(*) AS n FROM goals"
            " GROUP BY problem, status"):
        goal_counts.setdefault(str(r["problem"]), {})[str(r["status"])] = \
            int(r["n"])

    # Leases are only live work while their owner (the daemon) is the
    # running one — a dead owner's lease is residue awaiting reclaim,
    # not an agent (it rendered as "1 agent running now" for 8 days).
    inflight: dict[str, int] = {}
    live_pid = _live_daemon_pid(daemon)
    if live_pid is not None:
        for r in conn.execute(
                "SELECT problem, COUNT(*) AS n FROM queue"
                " WHERE owner_pid = ? GROUP BY problem", (live_pid,)):
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
        progressed = any(counts.get(s, 0) for s in
                         ("open", "attempting", "proved", "shelved",
                          "pending_strategist_review"))
        chip = _refine_chip(
            chip, working=_working(conn, daemon, name),
            progressed=progressed, queued=queued.get(name, 0))
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
                   problem: str, *,
                   daemon: "dict | None" = None) -> dict | None:
    """Full problem view: goal DAG (nodes + strategy edges), strategist
    decision timeline, proofs file list. `daemon` gates the liveness
    claims (status chip, per-goal in-flight pulse) exactly as board()."""
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

    # Live-work signal per goal: a queue row leased BY THE RUNNING
    # daemon means a worker is on it right now — the constellation
    # pulses that star. A dead owner's lease is residue, not a worker.
    inflight_goals: set[int] = set()
    live_pid = _live_daemon_pid(daemon)
    if live_pid is not None:
        for r in conn.execute(
                "SELECT target_id FROM queue WHERE problem = ?"
                " AND target_kind = 'Goal' AND owner_pid = ?",
                (problem, live_pid)):
            try:
                inflight_goals.add(int(r["target_id"]))
            except (TypeError, ValueError):
                pass

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
            "in_flight": int(g["id"]) in inflight_goals,
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

    # Dependency edges for Forward-built problems: strategies only exist
    # for Backward decompositions, so an all-forward constellation has
    # no structural edges — but the Ingest-time review snapshot carries
    # each deliverable's kernel anchor closure. Derive anchor→deliverable
    # edges from it (read-side, no gateway; best-effort name matching).
    anchor_edges: list[dict] = []
    try:
        from ..quality import review as _review
        snap = _review.load_review_snapshot(conn, problem)
        if snap is not None:
            slug_to_id = {g["slug"]: g["id"] for g in goals}
            prefix = f"Problems.{problem}."
            seen_pairs: set[tuple[int, int]] = set()
            for d in snap[0].get("deliverables", []):
                did = slug_to_id.get(str(d.get("slug", "")))
                if did is None:
                    continue
                for a in d.get("anchors", []):
                    # anchors are {kind, module, name} dicts (older
                    # snapshots may carry bare strings)
                    name = str(a.get("name", "")) if isinstance(a, dict) \
                        else str(a)
                    if name.startswith(prefix):
                        name = name[len(prefix):]
                    # ctor/companion names attribute to their parent
                    # decl (toy_list.cons → toy_list)
                    slug = name.split(".", 1)[0]
                    aid = slug_to_id.get(slug)
                    if (aid is not None and aid != did
                            and (aid, did) not in seen_pairs):
                        seen_pairs.add((aid, did))
                        anchor_edges.append({"from": aid, "to": did})
    except Exception:  # noqa: BLE001 — enrichment only, never fatal
        anchor_edges = []

    proofs_dir = db.problem_dir(workspace, problem) / "proofs"
    proof_files = sorted(
        f.name for f in proofs_dir.glob("*.lean")) if proofs_dir.is_dir() \
        else []

    awaiting = db.problem_has_awaiting_human(conn, problem)
    stalled = db.is_problem_stalled(conn, problem)
    chip = _status_chip(
        awaiting=awaiting,
        signoff=bool(prow["ingest_signoff_pending"]),
        bridged=prow["library_bridged_at"] is not None,
        ingested=prow["ingested_at"] is not None,
        stalled=stalled,
    )
    queued_n = conn.execute(
        "SELECT COUNT(*) FROM queue WHERE problem = ?",
        (problem,)).fetchone()[0]
    progressed = any(g["status"] in ("open", "attempting", "proved",
                                     "shelved",
                                     "pending_strategist_review")
                     for g in goals)
    working = _working(conn, daemon, problem)
    chip = _refine_chip(
        chip, working=working,
        progressed=progressed, queued=int(queued_n))
    # Same config source the dispatcher reads at startup — the serve
    # process isn't the daemon, so read it fresh (heat-ring denominator).
    from ..core import config as _config
    try:
        shelve_threshold = int(_config.get(
            "dispatch.shelve_threshold", default=8,
            env_var="ASTERISM_SHELVE_THRESHOLD", cast=int,
            workspace=workspace))
    except Exception:  # noqa: BLE001 — presentation hint, never fatal
        shelve_threshold = 8
    return {
        "name": str(prow["name"]),
        "status": chip,
        # is a live daemon actually on this problem right now? Lets the
        # UI stop dressing DB residue (goals stuck "attempting" after a
        # force stop) as live activity.
        "engine_working": working,
        "shelve_threshold": shelve_threshold,
        "created_at": str(prow["created_at"]),
        "ingested_at": prow["ingested_at"],
        "library_bridged_at": prow["library_bridged_at"],
        "strategist_directive": prow["strategist_directive"],
        "goals": goals,
        "strategies": strategies,
        "strategy_edges": edges,
        "anchor_edges": anchor_edges,
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
    strategies = [{
        "id": int(r["id"]),
        "status": str(r["status"]),
        "created_by": str(r["created_by"]),
        "subgoal_count": int(r["n"]),
    } for r in conn.execute(
        "SELECT s.id, s.status, s.created_by,"
        " (SELECT COUNT(*) FROM strategy_subgoals ss"
        "  WHERE ss.strategy_id = s.id) AS n"
        " FROM strategies s WHERE s.goal_id = ? ORDER BY s.id DESC",
        (goal_id,))]
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
        "strategies": strategies,
    }


def strategy_detail(conn: sqlite3.Connection, problem: str,
                    strategy_id: int) -> dict | None:
    """Strategy drill-down: the decomposition's own record —
    proposal_md (the agent's reasoning), status, subgoals."""
    s = conn.execute(
        "SELECT s.id, s.goal_id, s.status, s.proposal_md, s.created_by,"
        " s.created_at, g.problem, g.slug AS goal_slug"
        " FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE s.id = ? AND g.problem = ?",
        (strategy_id, problem)).fetchone()
    if s is None:
        return None
    subgoals = [{
        "id": int(r["id"]),
        "slug": str(r["slug"]),
        "status": str(r["status"]),
        "position": int(r["position"]),
    } for r in conn.execute(
        "SELECT g.id, g.slug, g.status, ss.position"
        " FROM strategy_subgoals ss JOIN goals g ON g.id = ss.subgoal_id"
        " WHERE ss.strategy_id = ? ORDER BY ss.position",
        (strategy_id,))]
    dead = []
    for r in conn.execute(
            "SELECT id, pipeline_id, failure_reason, failure_detail, ts"
            " FROM dead_attempts"
            " WHERE target_kind = 'Strategy' AND target_id = ?"
            " ORDER BY id DESC LIMIT 20", (strategy_id,)):
        dead.append({
            "id": int(r["id"]),
            "pipeline_id": str(r["pipeline_id"]),
            "failure_reason": str(r["failure_reason"]),
            "failure_detail": r["failure_detail"],
            "ts": str(r["ts"]),
        })
    return {
        "id": int(s["id"]),
        "goal_id": int(s["goal_id"]),
        "goal_slug": str(s["goal_slug"]),
        "status": str(s["status"]),
        "proposal_md": str(s["proposal_md"] or ""),
        "created_by": str(s["created_by"]),
        "created_at": str(s["created_at"]),
        "subgoals": subgoals,
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


def telemetry_usage(conn: sqlite3.Connection, *,
                    since: "str | None" = None) -> dict:
    """spawn_usage aggregation: totals per problem and per (problem,
    pipeline kind). `since` (an ISO timestamp, same format as the `ts`
    column) restricts the window — pass the running daemon's start time
    to get THIS run's burn instead of the all-time ledger."""
    per_problem: dict[str, dict] = {}
    where = " WHERE ts >= ?" if since else ""
    params: tuple = (since,) if since else ()
    for r in conn.execute(
            "SELECT COALESCE(problem, '') AS problem, kind,"
            " COUNT(*) AS spawns,"
            " SUM(input_tokens) AS in_tok, SUM(output_tokens) AS out_tok,"
            " SUM(cache_read_tokens) AS cache_tok,"
            " SUM(turns) AS turns, SUM(wall_sec) AS wall"
            " FROM spawn_usage" + where + " GROUP BY problem, kind",
            params):
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


def paper_section(workspace: Path, pid: str,
                  anchor: str | None) -> dict | None:
    """One page-anchored section of a shelved paper's extracted text
    (charter §3.2 side-by-side). Page anchors are `## p.N` lines. When
    `anchor` is a page anchor, returns that page's block; otherwise the
    whole text is scanned for the first literal occurrence and the
    surrounding page is returned. None if the paper isn't shelved."""
    if "/" in pid or "\\" in pid or ".." in pid:
        return None
    path = workspace / "Papers" / pid / "text.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    a = (anchor or "").strip()
    # Non-page anchor (free-text ref): locate it, then serve its page.
    if a and not a.startswith("## p.") and a in text:
        page_start = text.rfind("\n## p.", 0, text.index(a))
        if page_start >= 0:
            a = text[page_start + 1:text.index("\n", page_start + 1)]
        else:
            a = ""
    if a.startswith("## p."):
        idx = text.find(a + "\n")
        if idx < 0:
            idx = text.find(a)
        if idx >= 0:
            nxt = text.find("\n## p.", idx + 1)
            content = text[idx:nxt] if nxt > 0 else text[idx:]
            return {"pid": pid, "anchor": a, "found": True,
                    "content": content.strip()}
    # Fallback: unpaged source or unknown anchor — first 4KB as context.
    return {"pid": pid, "anchor": a or None, "found": False,
            "content": text[:4096]}


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
