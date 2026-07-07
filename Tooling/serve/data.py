"""Read-side aggregation for the serve API.

Every function here takes a read-only connection (`db.connect_readonly`)
and returns JSON-shaped dicts. Status semantics are NEVER derived here
when a state-layer predicate exists (charter §1-3): stalled =
`db.problems_stalled`, awaiting_human = `db.problem_has_awaiting_human`
(batched via one SQL pass), sign-off = `problems.ingest_signoff_pending`.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from ..pipeline.librarian.astslice import _library_module_of
from ..quality.librarian.gates import IMPORT_LINE_PATTERN
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


def _refine_chip(chip: str, *, working: bool, scoped: bool,
                 progressed: bool, queued: int) -> str:
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
    if chip in ("stalled", "proving") and working and scoped:
        # A live daemon scoped to THIS problem IS the work signal, even
        # before the first goal exists — a freshly-Run problem read
        # "idle" through the whole gateway warm-up (Test.Test3).
        return "proving"
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
            scoped=bool(daemon and daemon.get("scope")),
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


# ---------------------------------------------------------------------
# Citation edges (constellation truth): a proof file citing a sibling
# does it with `import Problems.<p>.proofs.L_<slug>` — the exact
# dependency lake sees. Read-side extraction for VISUALIZATION only
# (soundness citation checks live in db.classify_cited_slug /
# pipeline._cite_gate; this regex never gates anything). Per-file
# mtime cache: the board polls every 2s and a problem can have
# hundreds of proof files — stat everything, re-read only changes.
# ---------------------------------------------------------------------

_CITE_RE = re.compile(
    r"^import\s+Problems\.([\w.]+)\.proofs\.L_([A-Za-z0-9_']+)",
    re.MULTILINE)

#: path str -> (mtime_ns, [(problem, slug), ...])
_cite_file_cache: "dict[str, tuple[int, list[tuple[str, str]]]]" = {}


def _scan_imports(fp: Path) -> "list[tuple[str, str]]":
    """Cached `import Problems.<p>.proofs.L_<slug>` scan of one file.
    Missing files / read errors yield [] — presentation never fails."""
    key = str(fp)
    try:
        mtime = fp.stat().st_mtime_ns
    except OSError:
        _cite_file_cache.pop(key, None)
        return []
    cached = _cite_file_cache.get(key)
    if cached is None or cached[0] != mtime:
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        cites = [(m.group(1), m.group(2))
                 for m in _CITE_RE.finditer(text)]
        _cite_file_cache[key] = (mtime, cites)
    return _cite_file_cache[key][1]


def _citation_edges(workspace: Path, problem: str,
                    goals: "list[dict]",
                    strategies: "list[dict] | None" = None,
                    strategy_edges: "list[dict] | None" = None,
                    ) -> "list[dict]":
    """[{from: cited goal id, to: citing goal id}] within `problem`,
    from proof-file import lines.

    Two homes of truth. A goal's own `L_<slug>.lean` rarely imports
    siblings — the assembling proof of a Backward strategy lives in its
    scratch patch (`strategies.scratch_path`), and THAT is where most
    citations happen (banach_tarski: 248 of 261 sibling import lines).
    A succeeded strategy's non-child imports are the goal's citations;
    its child imports are the hierarchy already drawn as bundle arms.
    Without the scratch scan every Forward brick consumed by an
    assembly floated unlinked and the sky shattered (bt: 10 edges
    where 79 exist)."""
    slug_to_id = {g["slug"]: g["id"] for g in goals}
    out: list[dict] = []
    seen: set[tuple[int, int]] = set()

    def emit(prob: str, slug: str, citer_id: int,
             exclude: "set[int]") -> None:
        if prob != problem:
            return  # cross-problem import — not this sky's edge
        tid = slug_to_id.get(slug)
        if tid is None or int(tid) == citer_id or int(tid) in exclude:
            return
        pair = (int(tid), citer_id)
        if pair not in seen:
            seen.add(pair)
            out.append({"from": pair[0], "to": pair[1]})

    for g in goals:
        for prob, slug in _scan_imports(workspace / str(g["lean_path"])):
            emit(prob, slug, int(g["id"]), set())

    strat_kids: "dict[int, set[int]]" = {}
    for e in strategy_edges or []:
        strat_kids.setdefault(int(e["strategy_id"]), set()).add(
            int(e["subgoal_id"]))
    for s in strategies or []:
        sp = str(s.get("scratch_path") or "")
        if str(s.get("status")) != "succeeded" or not sp:
            continue
        for prob, slug in _scan_imports(workspace / sp):
            emit(prob, slug, int(s["goal_id"]),
                 strat_kids.get(int(s["id"]), set()))
    return out


def _comment_block(lines: "list[str]", start: int, slug: str,
                   siblings: "list[str]") -> str:
    """Collect the `--` comment run from `start`, stopping at a
    non-comment line or at a SIBLING sub-goal's anchor."""
    out = []
    for ln in lines[start:]:
        s = ln.strip()
        if not s.startswith("--"):
            break
        if out and (re.search(r"Sub-goal\s", s)
                    or any(sib != slug and sib in s for sib in siblings)):
            break
        out.append(s.lstrip("-").strip())
    text = " ".join(out)
    text = re.sub(r"\s+", " ", text).strip()
    # the goal column already names the slug — drop the annotation's
    # own `Sub-goal A `slug`:` prefix (same fact twice) and md bold
    text = re.sub(r"^Sub-goal\s+\S+\s*(?:`[^`]*`\s*)?[:—-]\s*", "", text)
    return text.replace("**", "")[:300]


def _goal_docs(conn: sqlite3.Connection, problem: str) -> "dict[int, str]":
    """goal_id → its birth annotation, the best available prose:

    - backward goals: the parent strategy `proposal_md`'s slug-anchored
      `--` comment block (the decomposer annotates every sub-goal);
      when the prose names hypotheses instead of the minted slug, fall
      back to the proposal's LEADING comment block — the decomposition's
      overall story, still that goal's birth certificate.
    - forward/injected goals: the strategist decision brief's first
      paragraph (joined via `produced_goal_id`).

    Display-only prose for the goals table; the full type is one click
    away on the goal panel."""
    docs: "dict[int, str]" = {}
    # strategist briefs (Inject / MarkDeliverable produce goals)
    for r in conn.execute(
            "SELECT produced_goal_id AS gid, brief FROM strategist_decisions"
            " WHERE problem = ? AND produced_goal_id IS NOT NULL"
            " AND brief IS NOT NULL", (problem,)):
        body = re.sub(r"(?m)^#{1,4}\s.*$", "", str(r["brief"]))
        para = next((p.strip() for p in re.split(r"\n\s*\n", body)
                     if p.strip()), "")
        if para:
            docs[int(r["gid"])] = (
                re.sub(r"\s+", " ", para).replace("**", "")[:300])
    # backward sub-goals: parent proposal's comment blocks
    by_strategy: "dict[int, list[sqlite3.Row]]" = {}
    for r in conn.execute(
            "SELECT sg.strategy_id AS sid, sg.subgoal_id AS gid,"
            " g.slug AS slug, s.proposal_md AS md"
            " FROM strategy_subgoals sg"
            " JOIN goals g ON g.id = sg.subgoal_id"
            " JOIN strategies s ON s.id = sg.strategy_id"
            " WHERE g.problem = ?", (problem,)):
        by_strategy.setdefault(int(r["sid"]), []).append(r)
    for rows in by_strategy.values():
        md = rows[0]["md"] or ""
        lines = md.splitlines()
        siblings = [str(r["slug"]) for r in rows]
        lead = next((i for i, ln in enumerate(lines)
                     if ln.strip().startswith("--")), None)
        for r in rows:
            gid, slug = int(r["gid"]), str(r["slug"])
            if gid in docs:
                continue  # a strategist brief outranks the proposal
            anchor = next((i for i, ln in enumerate(lines)
                           if ln.strip().startswith("--") and slug in ln),
                          None)
            block = (_comment_block(lines, anchor, slug, siblings)
                     if anchor is not None else
                     _comment_block(lines, lead, slug, siblings)
                     if lead is not None else "")
            if block:
                docs[gid] = block
    return docs


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
    # `workers` is the same truth as a roster ("what is each agent
    # doing"), the cockpit's run-strip data (demo/ stats panel lineage).
    inflight_goals: set[int] = set()
    workers: list[dict] = []
    live_pid = _live_daemon_pid(daemon)
    if live_pid is not None:
        for r in conn.execute(
                "SELECT q.kind AS kind, q.target_kind AS tk,"
                " q.target_id AS tid, q.leased_at AS leased_at, g.slug AS slug"
                " FROM queue q LEFT JOIN goals g ON q.target_kind = 'Goal'"
                " AND g.id = CAST(q.target_id AS INTEGER)"
                " WHERE q.problem = ? AND q.owner_pid = ?"
                " ORDER BY q.leased_at", (problem, live_pid)):
            if str(r["tk"]) == "Goal":
                try:
                    inflight_goals.add(int(r["tid"]))
                except (TypeError, ValueError):
                    pass
            workers.append({
                "kind": str(r["kind"]),
                "slug": r["slug"] if r["slug"] is not None else str(r["tid"]),
                "leased_at": r["leased_at"],
            })

    goal_docs = _goal_docs(conn, problem)
    disproofs = _disproof_links(conn, problem)
    goals = []
    for g in conn.execute(
            "SELECT id, slug, status, kind, origin, depth, detached,"
            " attempts, alias_target_id, is_deliverable, statement,"
            " lean_path, created_at FROM goals WHERE problem = ?"
            " ORDER BY id", (problem,)):
        goals.append({
            "id": int(g["id"]),
            "doc": goal_docs.get(int(g["id"])),
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
            # AttemptDisproof linkage (read-side): this goal IS ¬target
            "disproof_of": disproofs.get(int(g["id"])),
        })

    goal_ids = {g["id"] for g in goals}
    strategies = []
    for s in conn.execute(
            "SELECT id, goal_id, status, created_by, created_at,"
            " scratch_path"
            " FROM strategies ORDER BY id"):
        if int(s["goal_id"]) in goal_ids:
            strategies.append({
                "id": int(s["id"]),
                "goal_id": int(s["goal_id"]),
                "status": str(s["status"]),
                "created_by": str(s["created_by"]),
                "created_at": str(s["created_at"]),
                "scratch_path": str(s["scratch_path"] or ""),
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
        scoped=bool(daemon and daemon.get("scope")),
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
        # roster of the running daemon's leased units on this problem
        # (kind + goal slug + leased_at) — empty when nothing runs
        "workers": workers,
        "shelve_threshold": shelve_threshold,
        "created_at": str(prow["created_at"]),
        "ingested_at": prow["ingested_at"],
        "library_bridged_at": prow["library_bridged_at"],
        "strategist_directive": prow["strategist_directive"],
        "goals": goals,
        "strategies": strategies,
        "strategy_edges": edges,
        "anchor_edges": anchor_edges,
        # proof-file import citations (the DAG's cross-links): what the
        # tree views under-report — a Forward product cited by two
        # nodes has real structure
        "citation_edges": _citation_edges(
            workspace, problem, goals, strategies, edges),
        "decisions": decisions,
        "proof_files": proof_files,
    }


def _disproof_links(conn: sqlite3.Connection,
                    problem: str) -> "dict[int, dict]":
    """produced ¬P goal id → {id, slug} of the target P, from
    AttemptDisproof decision rows (the framework's mechanical linkage —
    no schema, no name-pattern guessing). A star that IS a disproof
    must say so wherever it is read: the sky dresses a proved negation
    exactly like ordinary success otherwise."""
    out: dict[int, dict] = {}
    for r in conn.execute(
            "SELECT d.produced_goal_id AS neg, g.id AS tid, g.slug AS slug"
            " FROM strategist_decisions d"
            " JOIN goals g ON g.id = d.target_id"
            " WHERE d.problem = ? AND d.decision_kind = 'AttemptDisproof'"
            " AND d.produced_goal_id IS NOT NULL", (problem,)):
        out[int(r["neg"])] = {"id": int(r["tid"]), "slug": str(r["slug"])}
    return out


def goal_detail(conn: sqlite3.Connection, problem: str,
                goal_id: int,
                workspace: "Path | None" = None) -> dict | None:
    """Goal drill-down: full row + dead-attempt forensics (most recent
    first, capped). With `workspace`, also the declaration source —
    the proof file minus its import prelude (a node IS its Lean text;
    the panel shows `name : statement := proof` as written)."""
    g = conn.execute(
        "SELECT * FROM goals WHERE id = ? AND problem = ?",
        (goal_id, problem)).fetchone()
    if g is None:
        return None
    proof_text = None
    src = g["lean_path"]
    if workspace is not None:
        # the winning route's scratch patch is the real proof — the
        # goal's own file is often a two-line delegate
        # (`def main := @...sNNN`); readers came for the tactics
        win = conn.execute(
            "SELECT scratch_path FROM strategies WHERE goal_id = ?"
            " AND status = 'succeeded' AND scratch_path != ''"
            " ORDER BY id DESC LIMIT 1", (goal_id,)).fetchone()
        if win is not None:
            src = win["scratch_path"]
        try:
            text = (workspace / str(src)).read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        # drop import lines wherever they sit (a header comment may
        # precede them and is worth keeping — it is the agent's own
        # narration); collapse the blank run they leave behind
        kept = [ln for ln in text.splitlines()
                if not ln.startswith("import ")]
        out_lines: list[str] = []
        for ln in kept:
            if not ln.strip() and out_lines and not out_lines[-1].strip():
                continue
            out_lines.append(ln)
        proof_text = "\n".join(out_lines).strip()[:40000] or None
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
        "disproof_of": _disproof_links(conn, problem).get(int(g["id"])),
        "proof_text": proof_text,
        # the file the source above was actually read from (the scratch
        # when a winning route exists) — the panel's path label must
        # name what it shows
        "source_path": str(src),
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


# ---------------------------------------------------------------------
# Library chapter — the harvested modules of ONE problem, read for
# humans. The Library exists for readability (near-Mathlib files, fit
# to upstream or to read), so its reading surface shows the CURATED
# text: module docstrings as prose, per-decl docstrings, and the
# kernel-true signature from the declInfo oracle (stored at bridge
# time). File parsing here is read-side visualization only — nothing
# it extracts feeds soundness (same standing as `_citation_edges`).
# ---------------------------------------------------------------------

_MODULE_DOC_RE = re.compile(r"/-!(.*?)-/", re.S)
_DOCSTRING_RE = re.compile(r"/--(.*?)-/", re.S)
_DECL_RE = re.compile(
    r"^(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+)?(?:private\s+|protected\s+)?"
    r"(theorem|lemma|def|abbrev|structure|class|instance|inductive|alias)\s+"
    r"([A-Za-z0-9_'₀-₉α-ω.]+)",
    re.M)
# the one spelling of a Lean import line (public/private prefixes,
# leading whitespace — gates.py owns it), compiled for whole-text scans
_IMPORT_RE = re.compile(IMPORT_LINE_PATTERN, re.M)


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


def _scan_library_file(
        text: str,
) -> "tuple[str, dict[str, tuple[int, str, str, str, str | None]], list[str]]":
    """(module_doc, {short_decl_name: (line, docstring, kind, stmt,
    source)}, imports). `line` is 1-based — same domain as the
    oracle-backed `library_decls.src_line`, so the two sort keys mix
    cleanly. `source` is the decl's full source block (attributes +
    header + body, docstring excluded) — the chapter's run state seeds
    an editor with it."""
    m = _MODULE_DOC_RE.search(text)
    module_doc = m.group(1).strip() if m else ""
    docs: "dict[str, tuple[int, str, str, str, str | None]]" = {}
    doc_ends = [(d.end(), d.group(1).strip()) for d in _DOCSTRING_RE.finditer(text)]
    matches = list(_DECL_RE.finditer(text))
    for i, dm in enumerate(matches):
        name = dm.group(2).split(".")[-1]
        if name in docs:
            continue  # first occurrence wins (aliases repeat names)
        doc = ""
        for end, body in doc_ends:
            if end > dm.start():
                break
            # attached iff only whitespace/attributes/line comments
            # separate them (corpus writes `--` notes between doc and
            # decl; those must not orphan the docstring)
            gap = text[end:dm.start()]
            if re.fullmatch(r"(?:\s|@\[[^\]]*\]|--[^\n]*)*", gap):
                doc = body
        nxt = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        src = text[dm.start():nxt].rstrip()
        # the tail may be the NEXT decl's docstring / section header /
        # `... in`-modifier lines (set_option, open, attributes) or an
        # `end Foo` namespace closer — all belong to what follows, not
        # to this decl; strip until the block ends in real content
        while True:
            tail = re.search(
                r"\n\s*(?:/(?:--|-!)(?:(?!-/)[\s\S])*-/|end\s+[\w.]+"
                r"|(?:set_option|open)[^\n]*\bin|@\[[^\]]*\]"
                r"|--[^\n]*)\s*$", src)
            if not tail:
                break
            src = src[:tail.start()].rstrip()
        docs[name] = (text.count("\n", 0, dm.start()) + 1, doc,
                      dm.group(1), _stmt_head(text, dm.start()),
                      src or None)
    return module_doc, docs, _IMPORT_RE.findall(text)


#: path str -> (mtime_ns, module_doc, docs, imports, word-set) — the
#: _cite_file_cache pattern: stat everything, re-read only changes.
#: The chapter is polled every 30s; steady-state must be ~stat-only.
_chapter_scan_cache: "dict[str, tuple[int, str, dict, list[str], frozenset]]" = {}


def _scanned_library_file(
        workspace: Path, path: str,
) -> "tuple[str, dict[str, tuple[int, str, str, str]], list[str], frozenset]":
    """Mtime-memoized `_scan_library_file` plus the file's whole-word
    token set — `short in words` is equivalent to the boundary-guarded
    regex search because decl short names are single `[\\w']+` tokens."""
    fp = workspace / path
    try:
        mtime = fp.stat().st_mtime_ns
    except OSError:
        _chapter_scan_cache.pop(path, None)
        return "", {}, [], frozenset()
    cached = _chapter_scan_cache.get(path)
    if cached is None or cached[0] != mtime:
        try:
            # errors="replace": presentation must never fail the page
            # (same policy as _cite_file_cache)
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:  # transient read failure — retry next request
            return "", {}, [], frozenset()
        module_doc, docs, imports = _scan_library_file(text)
        cached = (mtime, module_doc, docs, imports,
                  frozenset(re.findall(r"[\w']+", text)))
        _chapter_scan_cache[path] = cached
    return cached[1], cached[2], cached[3], cached[4]


def library_chapter(conn: sqlite3.Connection, workspace: Path,
                    problem: str) -> "dict | None":
    """One bridged problem's contributed Library modules, in import
    order, each decl carrying its docstring + oracle signature and its
    goal-side meaning (claim = deliverable, def-kind = vocabulary)."""
    # the one bridged+placed definition (db.bridged_library_index),
    # narrowed to this problem; rows carry library_bridged_at
    rows = db.bridged_library_index(conn, problem=problem).get(problem, [])
    if not rows:
        return None
    # goal-side flag only: kind comes from library_decls.decl_kind
    # (kernel-true since v24; goals.kind would duplicate it worse)
    deliverable = {
        str(g["slug"]): bool(g["is_deliverable"])
        for g in conn.execute(
            "SELECT slug, is_deliverable FROM goals WHERE problem = ?",
            (problem,))}

    per_file: "dict[str, list[sqlite3.Row]]" = {}
    for r in rows:
        per_file.setdefault(str(r["target_file"] or ""), []).append(r)
    scanned = {path: _scanned_library_file(workspace, path)
               for path in per_file}

    # Import order tells the story: a module comes after the siblings
    # it imports (Kahn; ties keep path order for determinism).
    mod_of = {path: _library_module_of(path) for path in per_file}
    mod_paths = {v: k for k, v in mod_of.items()}
    deps_of = {path: [d for d in scanned[path][2]
                      if d in mod_paths and d != mod_of[path]]
               for path in per_file}
    ordered: "list[str]" = []
    pending = sorted(per_file)
    placed: "set[str]" = set()
    while pending:
        progressed = False
        for path in list(pending):
            if all(mod_paths[d] in placed for d in deps_of[path]):
                ordered.append(path)
                placed.add(path)
                pending.remove(path)
                progressed = True
        if not progressed:  # import cycle can't happen; guard anyway
            ordered.extend(pending)
            break

    # Cross-module usage: in how many OTHER modules of this problem
    # does the decl's name appear? Ingest weakens the anchor/claim
    # flags (older harvests never had them), but a lemma the other
    # files keep reaching for is a keystone by demonstration — the
    # honest importance weight for the highlights view. Whole-word
    # heuristic (blueprint precedent), display only.
    files = []
    for path in ordered:
        module_doc, docs, imports, _words = scanned[path]
        keyed: "list[tuple[int, dict]]" = []
        for r in per_file[path]:
            slug = str(r["slug"])
            short = str(r["target_name"] or slug).split(".")[-1]
            line, doc, file_kind, file_stmt, file_src = docs.get(
                short, (1 << 30, "", "", "", None))
            # oracle values win (v24: docstring/src_line stored at bridge;
            # docstring '' = confirmed none, NULL = pre-backfill row →
            # curated source text fallback)
            if r["docstring"] is not None:
                doc = r["docstring"]
            if r["src_line"] is not None:
                line = int(r["src_line"])
            used_by = sum(1 for q in per_file
                          if q != path and short in scanned[q][3])
            keyed.append((line, {
                "slug": slug,
                "name": r["target_name"],
                # oracle values win; older harvests fall back to the
                # curated source text (display only)
                "signature": r["signature"] or file_stmt or None,
                "decl_kind": r["decl_kind"] or file_kind or None,
                "doc": doc,
                # the decl's real source block — the run state seeds a
                # live editor with it (proof included, editable)
                "source": file_src,
                "is_deliverable": deliverable.get(slug, False),
                "used_by": used_by,
            }))
        keyed.sort(key=lambda t: t[0])  # source order = narrative
        decls = [d for _, d in keyed]
        files.append({
            "path": path,
            "module_doc": module_doc,
            "decls": decls,
            # within-problem import edges — the file-level sky
            "imports_within": [mod_paths[i] for i in imports
                               if i in mod_paths and mod_paths[i] != path],
        })
    return {
        "problem": problem,
        "bridged_at": rows[0]["library_bridged_at"],
        "files": files,
    }


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
    return {"problems": rows}


def papers_list(conn: "sqlite3.Connection | None",
                workspace: Path) -> dict:
    """The bookshelf: every shelved paper's meta + which problems cite
    it (reverse of problem_papers) + map staleness. Filesystem is the
    shelf's SoT; the DB only contributes bindings (conn optional so a
    fresh workspace still lists its shelf)."""
    from ..papers import shelf as _shelf
    root = _shelf.papers_root(workspace)
    bound: dict[str, list[dict]] = {}
    if conn is not None:
        try:
            for r in conn.execute(
                    "SELECT problem, paper_id, origin FROM problem_papers"
                    " ORDER BY problem"):
                bound.setdefault(str(r["paper_id"]), []).append(
                    {"problem": str(r["problem"]),
                     "origin": str(r["origin"])})
        except sqlite3.OperationalError:
            pass
    papers = []
    if root.is_dir():
        for pdir in sorted(root.iterdir()):
            if not pdir.is_dir():
                continue
            meta = _shelf.load_meta(workspace, pdir.name)
            if meta is None:
                continue  # not a shelf slot (stray dir)
            original = next(
                (f.name for f in pdir.glob("paper.*") if f.is_file()), None)
            papers.append({
                "id": meta.id,
                "source_name": meta.source_name,
                "pages": meta.pages,
                "chars": meta.chars,
                "original": original,
                "has_map": _shelf.map_path(workspace, meta.id).exists(),
                "map_stale": _shelf.map_is_stale(workspace, meta.id),
                "bound": bound.get(meta.id, []),
            })
    papers.sort(key=lambda p: p["source_name"].lower())
    return {"papers": papers}


def problem_papers_detail(conn: sqlite3.Connection, workspace: Path,
                          problem: str) -> dict:
    """One problem's citations: bindings joined with shelf meta (a
    binding whose shelf slot vanished still shows, flagged missing)."""
    from ..papers import shelf as _shelf
    out = []
    for r in db.paper_bindings(conn, problem):
        pid = str(r["paper_id"])
        meta = _shelf.load_meta(workspace, pid)
        out.append({
            "id": pid,
            "origin": str(r["origin"]),
            "reason": r["reason"],
            "source_name": meta.source_name if meta else None,
            "missing": meta is None,
        })
    return {"problem": problem, "papers": out}


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
