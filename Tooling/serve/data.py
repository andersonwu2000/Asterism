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
from ..state import db, transitions


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
# what a USE scan must not read: comments (rationale prose names
# siblings freely) and the structural lines whose own tokens collide
# with decl names (`namespace Problems.<p>` ends in the problem leaf —
# the slc def was named exactly that, and every file "used" it)
_USE_BLOCK_COMMENT_RE = re.compile(r"/-.*?-/", re.S)
_USE_NOISE_RE = re.compile(
    r"^\s*(?:import|namespace|end|open)\b[^\n]*|--[^\n]*", re.MULTILINE)

#: path str -> (mtime_ns, [(problem, slug), ...], use-scan body)
_cite_file_cache: "dict[str, tuple[int, list[tuple[str, str]], str]]" = {}


def _scan_proof_file(fp: Path) -> "tuple[list[tuple[str, str]], str]":
    """Cached per-file scan: the `import Problems.<p>.proofs.L_<slug>`
    lines plus the comment/structure-stripped body for use checks.
    Missing files / read errors yield empty — presentation never
    fails."""
    key = str(fp)
    try:
        mtime = fp.stat().st_mtime_ns
    except OSError:
        _cite_file_cache.pop(key, None)
        return [], ""
    cached = _cite_file_cache.get(key)
    if cached is None or cached[0] != mtime:
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], ""
        cites = [(m.group(1), m.group(2))
                 for m in _CITE_RE.finditer(text)]
        body = _USE_NOISE_RE.sub(
            " ", _USE_BLOCK_COMMENT_RE.sub(" ", text))
        _cite_file_cache[key] = (mtime, cites, body)
    return _cite_file_cache[key][1], _cite_file_cache[key][2]


def _uses_name(body: str, slug: str) -> bool:
    """Does the stripped body reference `slug` as a NAME — bare or as
    the final segment of a qualified path? An occurrence that continues
    with `.` or a word char is a namespace prefix / longer identifier,
    not a use (`Problems.Topology.slc.foo` names foo, not slc)."""
    return re.search(
        rf"(?<![\w']){re.escape(slug)}(?![\w'.])", body) is not None


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
    where 79 exist).

    An import line alone is NOT a citation: Backward inherits its
    ancestor's preamble, so dead imports ride down the whole subtree
    (slc: 28 of 30 edges into the statement def were inherited weight —
    a super-hub of nothing). The edge needs the cited NAME used in the
    citing body. Exception: an `instance` brick is consumed namelessly
    by typeclass resolution — there the import is the only evidence,
    and it stays sufficient."""
    slug_to_id = {g["slug"]: g["id"] for g in goals}
    nameless = {g["slug"] for g in goals
                if str(g.get("kind")) == "instance"}
    out: list[dict] = []
    seen: set[tuple[int, int]] = set()

    def emit(prob: str, slug: str, citer_id: int,
             exclude: "set[int]", body: str) -> None:
        if prob != problem:
            return  # cross-problem import — not this sky's edge
        tid = slug_to_id.get(slug)
        if tid is None or int(tid) == citer_id or int(tid) in exclude:
            return
        if slug not in nameless and not _uses_name(body, slug):
            return  # inherited/vestigial import — dead weight, not story
        pair = (int(tid), citer_id)
        if pair not in seen:
            seen.add(pair)
            out.append({"from": pair[0], "to": pair[1]})

    for g in goals:
        cites, body = _scan_proof_file(workspace / str(g["lean_path"]))
        for prob, slug in cites:
            emit(prob, slug, int(g["id"]), set(), body)

    strat_kids: "dict[int, set[int]]" = {}
    for e in strategy_edges or []:
        strat_kids.setdefault(int(e["strategy_id"]), set()).add(
            int(e["subgoal_id"]))
    for s in strategies or []:
        sp = str(s.get("scratch_path") or "")
        if str(s.get("status")) != "succeeded" or not sp:
            continue
        cites, body = _scan_proof_file(workspace / sp)
        for prob, slug in cites:
            emit(prob, slug, int(s["goal_id"]),
                 strat_kids.get(int(s["id"]), set()), body)
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
    # Who marked each deliverable, and whether that is the group that
    # faces the human (2026-08-13, user ruling). `is_deliverable` is a
    # plain "somebody marked it": the TOP group's Mark is a claim the
    # human signs off on, a sub-group's is a result handed up to its
    # parent to track. Both are worth drawing; drawing them the SAME is
    # what put 23 of union_closed's 24 diamonds on the map as things a
    # person was being asked to vouch for.
    #
    # Shipped as ownership rather than as a filter on purpose: the map
    # should distinguish, not hide. `db.deliverables` is where the
    # surfaces that must actually narrow (sign-off, harvest) do it.
    _top_gid = db.top_group_id(conn, problem)
    marked_by = {
        int(r["target_id"]): (r["group_id"] and int(r["group_id"]))
        for r in conn.execute(
            "SELECT target_id, group_id FROM strategist_decisions"
            " WHERE decision_kind = 'MarkDeliverable' AND problem = ?"
            " ORDER BY id", (problem,))
    }
    goals = []
    for g in conn.execute(
            "SELECT id, slug, status, kind, origin, depth, detached,"
            " attempts, alias_target_id, is_deliverable, statement,"
            " lean_path, created_at FROM goals WHERE problem = ?"
            " ORDER BY id", (problem,)):
        sig = _goal_signature(workspace, str(g["slug"]),
                              g["lean_path"], g["statement"])
        goals.append({
            # display signature WITH binders (context.goal_display_
            # signature, the engine's own fix for "statement = bare
            # conclusion"); null when the file adds nothing
            "signature": sig,
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
            # Which group's Mark this is, and the one bit the map needs
            # to draw it right: is it addressed to the human, or handed
            # up to a parent group? None on both when nothing marked it.
            "marked_by_group": marked_by.get(int(g["id"])),
            "human_facing_claim": bool(
                g["is_deliverable"] and _top_gid is not None
                and marked_by.get(int(g["id"])) == _top_gid),
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
    # v35 — group_id (who decided) and produced_group_id (what a
    # Delegate opened) exist only post-migration; the timeline reads
    # them when they are there and stays silent when they are not
    _dcols = {r[1] for r in conn.execute(
        "PRAGMA table_info(strategist_decisions)")}
    _gsel = ("" if "group_id" not in _dcols
             else ", group_id, produced_group_id")
    for d in conn.execute(
            "SELECT id, batch_id, trigger_kind, decision_kind, target_id,"
            " brief, reason, payload, outcome, outcome_detail,"
            " produced_goal_id, produced_strategy_id, created_at, updated_at"
            + _gsel +
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
            "group_id": (d["group_id"] if _gsel else None),
            "produced_group_id": (d["produced_group_id"] if _gsel else None),
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

    top_group_id = _top_group_id(conn, problem)
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
        # research mode (v30): the current Programme's rev, or null
        # before bootstrap — the UI shows the Programme tab only when
        # there is a Programme to read. v35: of the TOP group, whose
        # argument is the problem's own (a sub-group's chain restarts
        # at 1 and would otherwise overwrite this number).
        "programme_rev": _programme_rev(conn, problem, top_group_id),
        # revision events for the timeline: a proposal cycle (passed OR
        # rejected) leaves no strategist_decisions row, so hours of
        # argument were invisible there — b6_1's founding proposal
        # survived 5 rounds and the timeline showed two Injects
        # (owner report, 2026-07-19)
        "programme_events": _programme_events(conn, problem, top_group_id),
        # the discussion-group tree (v35): one charter, one Programme,
        # one strategist/adversary loop each. A problem with only its
        # top group reads exactly as it did before groups existed.
        "groups": groups_of(conn, problem),
    }


#: v35 — every group owns its own revision chain, numbered from 1. A
#: problem-wide read therefore interleaves N chains and its "latest
#: rev" is the max of unrelated numberings: rev 3 of one argument
#: displayed as the successor of rev 2 of another. Every read below
#: scopes to ONE group, defaulting to the top group — the one whose
#: argument the problem page is about.
def _group_clause(gid: "int | None") -> "tuple[str, tuple]":
    return (" AND group_id = ?", (gid,)) if gid is not None else ("", ())


def _programme_events(conn: sqlite3.Connection, problem: str,
                      group_id: "int | None" = None) -> "list[dict]":
    clause, args = _group_clause(group_id)
    try:
        return [{
            "rev": int(r["rev"]),
            "status": str(r["status"]),
            "rounds": int(r["rounds"]),
            "created_at": str(r["created_at"]),
        } for r in conn.execute(
            "SELECT rev, status, rounds, created_at"
            " FROM programme_revisions WHERE problem = ?" + clause +
            " ORDER BY id DESC LIMIT 100", (problem,) + args)]
    except sqlite3.OperationalError:
        return []  # pre-v30 DB


def _programme_rev(conn: sqlite3.Connection, problem: str,
                   group_id: "int | None" = None) -> "int | None":
    clause, args = _group_clause(group_id)
    try:
        row = conn.execute(
            "SELECT MAX(rev) FROM programme_revisions"
            " WHERE problem = ? AND status = 'passed'" + clause,
            (problem,) + args).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except sqlite3.OperationalError:
        return None  # pre-v30 DB opened read-only — no table, no tab


def programme(conn: sqlite3.Connection, problem: str,
              group_id: "int | None" = None) -> dict:
    """The Programme page read: current passed revision (full body) +
    the whole revision history (passed AND rejected, no bodies — the
    audit dialogue stays in the DB; design §2 keeps the render clean).

    Verdict reservations ride along for the current rev: they are the
    Adversary's on-the-record caveats, exactly what a reader signing
    off on the argument should see.

    One GROUP's chain (v35) — `group_id` defaults to the top group, the
    argument the problem page is about. `groups` names the others so a
    reader can tell that a delegated burden is arguing elsewhere."""
    if group_id is None:
        group_id = _top_group_id(conn, problem)
    clause, args = _group_clause(group_id)
    rows = conn.execute(
        "SELECT id, rev, status, verdict, rounds, created_at"
        " FROM programme_revisions WHERE problem = ?" + clause +
        " ORDER BY id DESC", (problem,) + args).fetchall()
    history = [{
        "rev": int(r["rev"]),
        "status": str(r["status"]),
        "rounds": int(r["rounds"]),
        "created_at": str(r["created_at"]),
    } for r in rows]
    cur = conn.execute(
        "SELECT rev, body, verdict, rounds, created_at"
        " FROM programme_revisions"
        " WHERE problem = ? AND status = 'passed'" + clause +
        " ORDER BY rev DESC LIMIT 1", (problem,) + args).fetchone()
    current = None
    if cur is not None:
        reservations: "list[str]" = []
        try:
            v = json.loads(cur["verdict"] or "{}")
            reservations = [str(x) for x in (v.get("reservations") or [])]
        except (TypeError, ValueError):
            pass
        current = {
            "rev": int(cur["rev"]),
            "body": str(cur["body"]),
            "rounds": int(cur["rounds"]),
            "created_at": str(cur["created_at"]),
            "reservations": reservations,
        }
    # (The previous passed body rode along here for a rev-to-rev diff.
    # The owner reads only the standing argument — 2026-08-07 — and a
    # whole spare body on every 15s poll is not worth carrying for a
    # panel nobody opens.)
    # The charter of the group being READ, in full — the reason this
    # argument exists at all. The cards carry a snippet for labels;
    # the whole claim belongs in the reading, not in a tooltip.
    charter = None
    if group_id is not None:
        row = conn.execute(
            "SELECT charter, parent_group_id FROM groups WHERE id = ?",
            (int(group_id),)).fetchone()
        if row is not None and row["parent_group_id"] is not None:
            charter = str(row["charter"] or "") or None
    return {"current": current, "history": history,
            "group_id": group_id, "charter": charter,
            "groups": groups_of(conn, problem)}


# ---------------------------------------------------------------------
# Timeline — one flat log whose every row reads `at | what | to whom`
# ---------------------------------------------------------------------

#: decision_kind → the log's verb. A CLOSED vocabulary: a row states
#: what happened in one token and NAMES the object it happened to.
#: Prose (the brief, the reason) is expansion material and never the
#: headline — a timeline whose rows opened with 1.3KB of roadmap
#: markdown was unreadable at a glance (owner, 2026-08-07). An unknown
#: kind keeps its engine name rather than being mislabelled.
_DECISION_VERB: "dict[str, str]" = {
    "Inject": "asked",
    "Reopen": "reopened",
    "ConfirmShelve": "shelved",
    "MarkDeliverable": "deliverable",
    "Ingest": "ingested",
    "FetchPaper": "paper",
    "Delegate": "handed_off",
    "ReturnToParent": "handed_back",
    "CloseGroup": "closed_group",
    "RequestUserAmend": "asked_you",
    "EmitDirective": "directive",
    "Noop": "held",
    "AttemptDisproof": "disproof",
}

#: decision outcomes that mean "the thing it asked for exists now" —
#: the moment the produced goal became real. Mirrors the UI's OK set;
#: `parse` failures and declines are NOT landings.
_LANDED_OUTCOMES = frozenset({
    "success", "accepted", "live_subgoal", "closed_subgoal", "proved",
})

#: goal statuses that are an end of the road — these get a dated event.
#: An open/attempting goal has no transition to date yet.
_TERMINAL_GOAL_STATES = {
    "proved": "proved",
    "shelved": "shelved",
    "disproved": "disproved",
    "dead": "dead",
}

#: `goal_events.to_status` → the log's verb (v36). Not every transition
#: is news: 'attempting' is a worker picking the goal up and 'open' from
#: 'attempting' is the same worker putting it down, which the attempt
#: rows already tell. A revival — 'open' from a SETTLED state — is news,
#: and gets its verb from the from-side below.
_TO_STATUS_VERB = {
    "proved": "proved",
    "shelved": "shelved",
    "disproved": "disproved",
    "dead": "dead",
    "frozen": "frozen",
    "pending_strategist_review": "for_review",
}
_SETTLED = transitions.GOAL_TERMINALS

#: how far along a goal's life each verb sits — the tiebreaker when a
#: brick is asked for and lands inside the same clock minute
_LIFE_RANK: "dict[str, int]" = {
    "opened": 0, "asked": 1, "reopened": 1, "hiccup": 2, "failed": 3,
    "deliverable": 6, "proved": 7, "shelved": 7, "disproved": 7,
    "dead": 7, "ingested": 8,
}

#: What a dispatch ASKED FOR, when its goal does not exist yet (a
#: failed or still-in-flight Inject). Used ONLY to LABEL such a row —
#: never to link, never as a gate signal; with no row to point at the
#: alternative is an anonymous event, which is worst exactly where the
#: reader most wants a name (the newest dispatches).
#:
#: The PATH is tried first and the prose second, because the path is a
#: convention the framework enforces (`proofs/L_<slug>.lean`) while the
#: sentence around it is the strategist's own wording — and that wording
#: moved: batches now say "Mint into `proofs/L_x.lean`" with no "mint
#: brick `x`" anywhere, so a prose-only reader labelled the newest rows
#: with the problem's name (owner spotted it on union_closed,
#: 2026-08-09).
#: Three readers, most-structural first. The PATH is the file the brick
#: will actually be called, and the framework enforces its shape. The
#: TITLE is the brief's own opening line and every brief has one, but it
#: is the strategist's composition. The PROSE phrase is the weakest and
#: the one already caught moving. When a brief carries several they
#: agree; when they disagree the file name is the fact.
_MINT_READERS = (
    re.compile(r"proofs/L_([A-Za-z0-9_']+)\.lean"),
    re.compile(r"^#\s*[`\"]([A-Za-z0-9_']+)[`\"]", re.M),
    re.compile(r"[Mm]int (?:brick|def) [`\"]([A-Za-z0-9_']+)[`\"]"),
)


def _asked_for(brief: str) -> "str | None":
    for rx in _MINT_READERS:
        m = rx.search(brief)
        if m:
            return m.group(1)
    return None


def _ev(at: str, kind: str, *, object_kind: str = "problem",
        label: str = "", goal_id: "int | None" = None,
        n: "int | None" = None, note: "str | None" = None,
        body: "str | None" = None, approx: bool = False,
        eid: str = "", batch_id: "str | None" = None,
        group_id: "int | None" = None,
        object_group_id: "int | None" = None) -> dict:
    # `group_id` = which ARGUMENT this event belongs to (v35). A problem
    # under real load runs several discussion groups at once — 7 on
    # simple_loop_conjecture, 4 on union_closed — and their bricks
    # interleave in one stream with nothing to tell them apart.
    # `object_group_id` is different: the group a handover row is ABOUT.
    return {
        "at": at, "kind": kind, "object_kind": object_kind,
        "label": label, "goal_id": goal_id, "n": n, "note": note,
        "body": body, "approx": approx, "id": eid,
        "batch_id": batch_id, "group_id": group_id,
        "object_group_id": object_group_id,
    }


def _logged_transitions(conn: sqlite3.Connection, problem: str,
                        goals: "list[dict]") -> "tuple[list[dict], set[int]]":
    """Goal state changes as the ENGINE RECORDED THEM (`goal_events`,
    v36 — appended inside `db.update_goal_status`, so it catches the
    operator's own amend escape hatch as well as every checked
    transition).

    Returns the events and the set of goals it speaks for: a goal with
    logged history is never reconstructed on top of.
    """
    by_id = {int(g["id"]): g for g in goals}
    out: "list[dict]" = []
    covered: "set[int]" = set()
    try:
        rows = conn.execute(
            "SELECT id, goal_id, from_status, to_status, event, reason, at"
            " FROM goal_events WHERE problem = ? ORDER BY at, id",
            (problem,)).fetchall()
    except sqlite3.OperationalError:
        return [], set()  # pre-v36 DB — reconstruction carries it all
    for r in rows:
        gid = int(r["goal_id"])
        if gid not in by_id:
            continue
        covered.add(gid)
        frm, to = str(r["from_status"] or ""), str(r["to_status"])
        verb = _TO_STATUS_VERB.get(to)
        if verb is None:
            # a revival is news; a worker picking the goal up is not
            if to == "open" and frm in _SETTLED:
                verb = "reopened"
            else:
                continue
        out.append(_ev(
            str(r["at"]), verb, object_kind="goal",
            label=str(by_id[gid]["slug"]), goal_id=gid,
            note=str(r["reason"] or "") or None,
            eid=f"e{int(r['id'])}"))
    return out, covered


def _transition_events(conn: sqlite3.Connection, problem: str,
                       goals: "list[dict]",
                       dec_rows: "list[sqlite3.Row]") -> "list[dict]":
    """When each goal reached its terminal state, for the goals the
    engine's own log does not cover — everything that happened before
    `goal_events` existed (v36).

    THE HONEST CAVEAT: this is RECONSTRUCTION. In order of trust:

      1. the succeeded pipeline that targeted the goal (`finished_at`)
      2. the producing decision's outcome write (`updated_at`) — when
         the batch step was recorded as landed
      3. `goals.updated_at`, marked `approx`

    (3) is last because that column is bumped by `attempts + 1`,
    `is_deliverable` and `integrity_verified` writes too: measured
    against (1)/(2) on Combinatorics.union_closed it agreed at the
    median and drifted +18min at p90, +43min worst case.
    """
    by_id = {int(g["id"]): g for g in goals}
    # (1) succeeded pipelines, latest per goal
    pipe: "dict[int, str]" = {}
    try:
        for r in conn.execute(
                "SELECT target_id, MAX(finished_at) AS at FROM pipelines"
                " WHERE target_kind = 'Goal' AND status = 'succeeded'"
                "   AND finished_at IS NOT NULL"
                " GROUP BY target_id"):
            try:
                gid = int(r["target_id"])
            except (TypeError, ValueError):
                continue
            if gid in by_id:
                pipe[gid] = str(r["at"])
    except sqlite3.OperationalError:
        pass
    # (2) the decision that produced the goal, once its outcome landed;
    # and (2b) the ConfirmShelve that set one aside — that decision IS
    # the shelving, so it dates it exactly.
    landed: "dict[int, str]" = {}
    shelved_by: "dict[int, str]" = {}
    for d in dec_rows:
        gid = d["produced_goal_id"]
        if (gid is not None and int(gid) in by_id
                and str(d["outcome"] or "") in _LANDED_OUTCOMES):
            landed[int(gid)] = str(d["updated_at"])
        if str(d["decision_kind"]) == "ConfirmShelve":
            try:
                tid = int(d["target_id"])
            except (TypeError, ValueError):
                continue
            if tid in by_id:
                shelved_by[tid] = str(d["created_at"])

    out: "list[dict]" = []
    for g in goals:
        kind = _TERMINAL_GOAL_STATES.get(str(g["status"]))
        if kind is None:
            continue
        gid = int(g["id"])
        # ConfirmShelve IS the shelving — its own row already says so.
        # (A ConfirmShelve on a goal that later revived stays: that one
        # is history, not a duplicate of the current state.)
        if kind == "shelved" and gid in shelved_by:
            continue
        at = pipe.get(gid) or landed.get(gid)
        approx = at is None
        if at is None:
            at = str(g["updated_at"])
        out.append(_ev(at, kind, object_kind="goal", label=str(g["slug"]),
                       goal_id=gid, approx=approx, eid=f"g{gid}"))
    return out


def _attempt_events(conn: sqlite3.Connection,
                    goals: "list[dict]") -> "list[dict]":
    """Failed attempts, numbered per goal in the order they happened.

    Infrastructure failures are split off as `hiccup`: the registry's
    own semantics — a provider/pipeline infra death never incremented
    `goals.attempts` — so counting them as attempts would tell the
    reader the machine tried more times than it did.
    """
    from ..state.failures import is_infra
    by_id = {int(g["id"]): g for g in goals}
    rows = []
    for r in conn.execute(
            "SELECT target_id, failure_reason, ts FROM dead_attempts"
            " WHERE target_kind = 'Goal' ORDER BY ts"):
        try:
            gid = int(r["target_id"])
        except (TypeError, ValueError):
            continue
        if gid in by_id:
            rows.append((gid, str(r["failure_reason"]), str(r["ts"])))
    out = []
    for i, (gid, reason, ts) in enumerate(rows):
        # NOT numbered. These rows are `dead_attempts` records — one per
        # failure the engine filed — and numbering them "attempt N"
        # claimed they were the engine's own attempt sequence. They are
        # not: measured on union_closed, `goals.attempts` disagrees in
        # BOTH directions (10 vs 6 recorded, 4 vs 6) because one spawn
        # can file two records (watchdog says stuck, then the spawn
        # times out) and some attempts burn the counter without filing
        # one. The reasons and their order are the evidence; the count
        # of tries belongs to whoever reads `goals.attempts`.
        out.append(_ev(ts, "hiccup" if is_infra(reason) else "failed",
                       object_kind="goal", label=str(by_id[gid]["slug"]),
                       goal_id=gid, note=reason, eid=f"a{i}-{gid}"))
    return out


def _decision_events(conn: sqlite3.Connection, problem: str,
                     dec_rows: "list[sqlite3.Row]",
                     goals: "list[dict]") -> "list[dict]":
    """The strategist's moves, each naming what it moved."""
    by_id = {int(g["id"]): g for g in goals}
    out = []
    for d in dec_rows:
        kind = str(d["decision_kind"])
        verb = _DECISION_VERB.get(kind, kind)
        try:
            payload = json.loads(d["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        brief = str(d["brief"] or "")
        reason = str(d["reason"] or "")
        gid = d["produced_goal_id"]
        if gid is None:
            gid = d["target_id"]
        if gid is None:
            gid = payload.get("target_goal_id")
        try:
            gid = int(gid) if gid is not None else None
        except (TypeError, ValueError):
            gid = None
        if gid not in by_id:
            gid = None
        okind, label, obj_group = "problem", problem, None
        if gid is not None:
            okind, label = "goal", str(by_id[gid]["slug"])
        elif kind == "FetchPaper":
            okind = "paper"
            label = str(payload.get("query") or reason or "a paper")
        elif kind in ("Delegate", "ReturnToParent", "CloseGroup"):
            okind = "group"
            g = d["produced_group_id"] if "produced_group_id" \
                in d.keys() else None
            obj_group = int(g) if g is not None else (
                int(payload["group_id"]) if isinstance(
                    payload.get("group_id"), int) else None)
            # a group NAMES itself in its Programme's title; its charter
            # is a paragraph and a poor label (same law as the tree)
            card = _group_lineage(conn, problem, group_card(conn, obj_group)) \
                if obj_group else None
            label = (card or {}).get("title") or (card or {}).get(
                "charter") or (f"group {obj_group}" if obj_group else problem)
        elif verb == "asked":
            # a dispatch whose brick does not exist yet (failed or still
            # in flight) — name what was ASKED FOR, or the row is anonymous
            asked = _asked_for(brief)
            if asked:
                okind, label = "unbuilt", asked
        note = reason or None
        if kind == "ReturnToParent" and payload.get("flavour"):
            note = f"{payload['flavour']} — {reason}" if reason \
                else str(payload["flavour"])
        own = d["group_id"] if "group_id" in d.keys() else None
        out.append(_ev(
            str(d["created_at"]), verb, object_kind=okind, label=label,
            goal_id=gid, note=note, body=brief or None,
            eid=f"d{int(d['id'])}", batch_id=d["batch_id"],
            group_id=int(own) if own is not None else None,
            object_group_id=obj_group))
    return out


def _goal_arguments(conn: sqlite3.Connection, problem: str,
                    dec_rows: "list[sqlite3.Row]",
                    goals: "list[dict]") -> "dict[int, int]":
    """goal id → the discussion group whose argument it serves.

    A commissioned brick inherits the group of the decision that asked
    for it. A subgoal nobody commissioned — cut out of a larger goal by
    a decomposition — serves the same argument as the goal it was cut
    from, so the attribution propagates down the strategy edges.
    """
    if "group_id" not in (dec_rows[0].keys() if dec_rows else ()):
        return {}
    arg: "dict[int, int]" = {}
    ids = {int(g["id"]) for g in goals}
    for d in dec_rows:
        gid, own = d["produced_goal_id"], d["group_id"]
        if gid is not None and own is not None and int(gid) in ids:
            arg[int(gid)] = int(own)
    parent: "dict[int, int]" = {}
    for r in conn.execute(
            "SELECT e.subgoal_id AS sub, s.goal_id AS parent"
            "  FROM strategy_subgoals e JOIN strategies s"
            "    ON s.id = e.strategy_id"):
        if int(r["sub"]) in ids and int(r["parent"]) in ids:
            parent[int(r["sub"])] = int(r["parent"])
    for gid in ids - set(arg):
        seen, cur = set(), gid
        while cur in parent and cur not in seen:
            seen.add(cur)
            cur = parent[cur]
            if cur in arg:
                arg[gid] = arg[cur]
                break
    return arg


#: how far apart the two records of one act may sit. They are written
#: in the same operation (measured: under 0.1s), so this is slack for
#: clock granularity, not a window in which two real shelvings could be
#: mistaken for one — those are hours apart.
_SAME_ACT_SEC = 120.0


def _already_said(said: "set", e: dict) -> bool:
    """Has a decision row already reported this goal's transition?"""
    from datetime import datetime
    for gid, kind, at in said:
        if gid != e["goal_id"] or kind != e["kind"]:
            continue
        try:
            delta = abs((datetime.fromisoformat(at)
                         - datetime.fromisoformat(e["at"])).total_seconds())
        except ValueError:
            continue
        if delta <= _SAME_ACT_SEC:
            return True
    return False


def problem_events(conn: sqlite3.Connection, problem: str) -> dict:
    """The Timeline read: one flat, uniform log.

    Every row is `at | what happened | to whom`, and every row NAMES an
    object — which is what lets a reader follow one brick's whole life
    (asked → attempt 2 → proved) by filtering on it. That reading was
    impossible while the log recorded only what the strategist decided:
    of 54 goals on union_closed, 52 reached `proved` and not one of
    those landings appeared here (owner, 2026-08-07).
    """
    goals = [dict(r) for r in conn.execute(
        "SELECT id, slug, status, origin, created_at, updated_at"
        " FROM goals WHERE problem = ?", (problem,))]
    _dcols = {r[1] for r in conn.execute(
        "PRAGMA table_info(strategist_decisions)")}
    _gsel = "" if "produced_group_id" not in _dcols \
        else ", produced_group_id, group_id"
    dec_rows = conn.execute(
        "SELECT id, batch_id, decision_kind, target_id, brief, reason,"
        " payload, outcome, produced_goal_id, created_at, updated_at"
        + _gsel +
        " FROM strategist_decisions WHERE problem = ?"
        " ORDER BY id DESC", (problem,)).fetchall()

    events = _decision_events(conn, problem, dec_rows, goals)
    logged, covered = _logged_transitions(conn, problem, goals)
    # A decision whose EXECUTION is a status write gets recorded twice:
    # once as what the strategist decided, once as what happened to the
    # goal. ConfirmShelve is the live instance (8 pairs on union_closed,
    # every delta under 0.1s — the status write rides the decision), and
    # Reopen has the same shape. Same fact, so one row; the DECISION
    # survives because it carries WHY, which the transition cannot.
    said = {(e["goal_id"], e["kind"], e["at"]) for e in events
            if e["goal_id"] is not None}
    events += [e for e in logged if not _already_said(said, e)]
    events += [e for e in _transition_events(conn, problem, goals, dec_rows)
               if e["goal_id"] not in covered]
    events += _attempt_events(conn, goals)

    # a goal nobody dispatched (a decomposition cut it out of its
    # parent) still has a birthday, and its insert dates it exactly
    asked = {e["goal_id"] for e in events
             if e["kind"] in ("asked", "reopened") and e["goal_id"]}
    for g in goals:
        if int(g["id"]) not in asked:
            events.append(_ev(str(g["created_at"]), "opened",
                              object_kind="goal", label=str(g["slug"]),
                              goal_id=int(g["id"]),
                              note=str(g["origin"]),
                              eid=f"o{int(g['id'])}"))

    # the argument's own landmarks — only revisions that LANDED ride the
    # default stream; a rejected proposal is a round of editing, not a
    # change to the record (owner, 2026-08-07)
    top = _top_group_id(conn, problem)
    # A revision NAMES itself in its own `# Title` — "programme" for
    # every row said only which surface it came from, not what changed
    # (owner, 2026-08-07). substr: the title is the first non-empty
    # line, and a body runs to tens of KB.
    titles: "dict[int, str]" = {}
    try:
        for r in conn.execute(
                "SELECT rev, substr(body, 1, 400) AS head FROM"
                " programme_revisions WHERE problem = ? AND group_id IS ?"
                " AND status = 'passed'", (problem, top)):
            t = _programme_title(str(r["head"] or ""))
            if t:
                titles[int(r["rev"])] = t
    except sqlite3.OperationalError:
        pass
    for r in _programme_events(conn, problem, top):
        passed = r["status"] == "passed"
        events.append(_ev(
            r["created_at"], "rev" if passed else "proposal",
            object_kind="programme",
            label=titles.get(r["rev"], "programme"), n=r["rev"],
            note=(None if r["rounds"] == 0 else
                  f"{r['rounds']} round{'' if r['rounds'] == 1 else 's'}"
                  " of review"),
            eid=f"p{r['rev']}-{r['created_at']}", group_id=top))

    # which argument each event serves — a decision knows its own group;
    # everything derived from a goal inherits the goal's
    arg = _goal_arguments(conn, problem, dec_rows, goals)
    for e in events:
        if e["group_id"] is None and e["goal_id"] is not None:
            e["group_id"] = arg.get(int(e["goal_id"]))

    # newest first; within one timestamp, later-in-life first — a brick
    # minted and landed inside the same minute must not read as having
    # been proved before it was asked for
    events.sort(key=lambda e: (e["at"], _LIFE_RANK.get(e["kind"], 5),
                               e["id"]), reverse=True)
    # Where the record starts. Below this line every goal landing is
    # dated by inference from the work that produced it; above it the
    # engine wrote the transition down itself. Three months from now
    # nobody will remember which half was which unless the surface
    # says so (backend, 2026-08-07).
    try:
        row = conn.execute(
            "SELECT MIN(at) FROM goal_events WHERE problem = ?",
            (problem,)).fetchone()
        log_since = str(row[0]) if row and row[0] is not None else None
    except sqlite3.OperationalError:
        log_since = None
    # names for the argument lenses. A problem with only its top group
    # reads exactly as it did before groups existed — the UI shows no
    # lens at all — so this list is furniture only when it is > 1.
    groups = [{
        "id": g["id"], "is_top": g["is_top"],
        "label": g.get("title") or g.get("charter") or f"group {g['id']}",
        "status": g["status"],
    } for g in groups_of(conn, problem)]
    return {"events": events, "log_since": log_since, "groups": groups}


# display-signature cache: mtime-keyed per lean file so the 3s detail
# poll doesn't re-read a hundred stubs (the underlying reader is the
# engine's context.goal_display_signature — ONE extraction, no serve
# dialect; #5, 2026-07-18)
_SIG_CACHE: "dict[str, tuple[float, str | None]]" = {}


def _goal_signature(workspace: Path, slug: str,
                    lean_path: "str | None",
                    statement: "str | None") -> "str | None":
    """Binders+conclusion display form, or None when the file offers
    nothing beyond the stored statement (alias bodies read as plumbing,
    not mathematics — the bare statement is more honest there)."""
    if not lean_path:
        return None
    key = f"{workspace}|{lean_path}"
    try:
        mtime = (workspace / str(lean_path)).stat().st_mtime
    except OSError:
        return None
    hit = _SIG_CACHE.get(key)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    from ..agent.context import goal_display_signature
    sig: "str | None" = goal_display_signature(
        workspace, slug, lean_path, statement)
    if (not sig or sig == str(statement or "")
            or ":= @" in sig or " : " not in sig):
        sig = None
    _SIG_CACHE[key] = (mtime, sig)
    return sig


#: How much of a charter a display surface carries inline. The whole
#: claim lives in the group's own read; a lane or a chip needs the
#: subject, not the paragraph.
_CHARTER_SNIP = 240


def _programme_title(body: str) -> "str | None":
    """The Programme's own `# Title` line — what the argument calls
    itself. Falls back to the first prose line for a body that opens
    without one; None when there is nothing to read."""
    for raw in body.splitlines():
        line = raw.strip()
        if line == "":
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        return line[:160] or None
    return None


def _charter_snippet(charter: str) -> str:
    one = " ".join(str(charter or "").split())
    return one[:_CHARTER_SNIP].rstrip() + "…" if len(one) > _CHARTER_SNIP \
        else one


def group_card(conn: sqlite3.Connection, group_id: int) -> "dict | None":
    """The display identity of one discussion group (v35).

    A group is one charter, one Programme, one strategist/adversary
    loop. The TOP group is the problem itself facing a human — it has
    no charter (its charter is the Manifest), and surfaces must not
    dress it up as a delegated burden: with no sub-groups anywhere,
    every display reads exactly as it did before groups existed.
    """
    try:
        r = conn.execute(
            "SELECT id, problem, parent_group_id, charter, status,"
            " anchor_goal_id, created_at FROM groups WHERE id = ?",
            (int(group_id),)).fetchone()
    except sqlite3.OperationalError:
        return None  # pre-v35 DB
    if r is None:
        return None
    return {
        "id": int(r["id"]),
        "problem": str(r["problem"]),
        "parent_id": (int(r["parent_group_id"])
                      if r["parent_group_id"] is not None else None),
        "is_top": r["parent_group_id"] is None,
        "charter": _charter_snippet(r["charter"]),
        "status": str(r["status"]),
        "anchor_goal_id": (int(r["anchor_goal_id"])
                           if r["anchor_goal_id"] is not None else None),
        "created_at": str(r["created_at"]),
    }


def _top_group_id(conn: sqlite3.Connection, problem: str) -> "int | None":
    """The problem's human-facing group — the one whose Programme and
    revision numbering a problem-level read means."""
    try:
        r = conn.execute(
            "SELECT id FROM groups WHERE problem = ?"
            " AND parent_group_id IS NULL", (problem,)).fetchone()
    except sqlite3.OperationalError:
        return None  # pre-v35 DB: revisions are problem-wide, as before
    return int(r["id"]) if r is not None else None


#: bricks listed per delivered group — the block names what a finished
#: group handed up; beyond this it stops being a list and becomes a
#: file, and the count still tells the truth.
_BRICKS_SHOWN = 40


def _group_lineage(conn: sqlite3.Connection, problem: str,
                   card: dict) -> dict:
    """Where a group sits in the ARGUMENT, not just in the tree.

    `opened_at_rev` is the revision of the parent whose batch delegated
    this claim — the one fact that ties the document to the tree: a
    reader of rev 6 can see that rev 2 and rev 3 each handed a burden
    out and whether it came back. `rev` is the group's OWN chain (every
    group numbers from 1). `bricks` are the goals its strategist
    commissioned — which survives delivery, unlike subtree ownership
    (a delivered group's goals fold into its parent's).
    """
    gid = int(card["id"])
    card["opened_at_rev"] = None
    if card.get("parent_id") is not None:
        row = conn.execute(
            "SELECT r.rev AS rev FROM groups g"
            " JOIN strategist_decisions d ON d.id = g.opened_by"
            " JOIN programme_revisions r ON r.batch_id = d.batch_id"
            "  AND r.problem = d.problem AND r.group_id = d.group_id"
            " WHERE g.id = ? LIMIT 1", (gid,)).fetchone()
        if row is not None:
            card["opened_at_rev"] = int(row["rev"])
    card["rev"] = _programme_rev(conn, problem, gid)
    # A group NAMES itself in its Programme's title line; the charter
    # is the reason it was handed the burden, which is a paragraph and
    # a poor label (owner, 2026-08-07). The charter still travels — as
    # a block inside the group's own read.
    card["title"] = None
    if card["rev"] is not None:
        row = conn.execute(
            "SELECT body FROM programme_revisions"
            " WHERE problem = ? AND group_id = ? AND status = 'passed'"
            " ORDER BY rev DESC LIMIT 1", (problem, gid)).fetchone()
        if row is not None:
            card["title"] = _programme_title(str(row["body"] or ""))
    bricks = conn.execute(
        "SELECT g.slug AS slug, g.id AS id, g.status AS status"
        "  FROM strategist_decisions d JOIN goals g"
        "    ON g.id = d.produced_goal_id"
        " WHERE d.problem = ? AND d.group_id = ?"
        "   AND d.produced_goal_id IS NOT NULL"
        " ORDER BY d.id", (problem, gid)).fetchall()
    proved = [{"id": int(b["id"]), "slug": str(b["slug"])}
              for b in bricks if str(b["status"]) == "proved"]
    card["bricks"] = len(bricks)
    card["bricks_proved"] = len(proved)
    # only a group that has HANDED ITS WORK UP carries the list: that
    # is the reading ("what may I cite now"); a group still arguing is
    # read through its own Programme, not through a brick inventory
    card["delivered_bricks"] = (proved[:_BRICKS_SHOWN]
                                if card["status"] == "delivered" else [])
    return card


def groups_of(conn: sqlite3.Connection, problem: str) -> "list[dict]":
    """Every group in the problem, top first then by age — the tree a
    reader needs to know exists before any of it can be shown, each
    carrying where it came from and what it produced."""
    try:
        rows = conn.execute(
            "SELECT id FROM groups WHERE problem = ?"
            " ORDER BY (parent_group_id IS NULL) DESC, id", (problem,)
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    for r in rows:
        card = group_card(conn, int(r["id"]))
        if card is not None:
            out.append(_group_lineage(conn, problem, card))
    return out


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


def goal_workarea_draft(workspace: Path, slug: str) -> "Path | None":
    """Freshest .lean draft in the workarea serving goal `slug`
    (matched by Context.md's '# Context for goal <slug>' heading —
    only the owning agent's context carries it as a heading, so a
    sibling merely CITING the slug never matches). The Formalizer
    drafts `patch.lean` here and only lands at commit, so this is the
    ONLY place its work exists until then — the run lane and the goal
    panel both read it."""
    marker = f"# Context for goal {slug}"
    best: "Path | None" = None
    best_m = -1.0
    try:
        entries = list((workspace / ".attempts").iterdir())
    except OSError:
        return None
    for d in entries:
        if d.name.startswith("_") or not d.is_dir():
            continue
        try:
            ctx = (d / "Context.md").read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            continue
        if marker not in ctx:
            continue
        try:
            for f in d.glob("*.lean"):
                if f.name.startswith("_"):
                    continue
                mt = f.stat().st_mtime
                if mt > best_m:
                    best_m = mt
                    best = f
        except OSError:
            continue
    return best


def _mtime_or(path: Path, default: float = -1.0) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return default


def _goal_source(conn: sqlite3.Connection, workspace: Path,
                 goal_id: int, slug: str,
                 lean_path: str) -> "tuple[str, str, int | None]":
    """(path, state, strategy_id) — WHICH text the panel should show for
    this goal, and what that text is.

    A node's own file is a `:= by sorry` stub for its whole working
    life: the decomposition lands in the ROUTE's file and the live
    attempt exists only in a workarea. Showing the stub told the reader
    nothing about how the goal was actually split (owner, 2026-08-01).
    Freshest meaningful text wins:

      winning_route — the route that closed it (its scratch IS the proof)
      open_route    — a route still open: how the goal is split right now
      in_flight     — an attempt writing this minute (scratch; may vanish)
      own_file      — no route, no draft: the goal's own file as it stands
    """
    src, state, sid = lean_path, "own_file", None
    row = conn.execute(
        "SELECT id, scratch_path, status FROM strategies"
        " WHERE goal_id = ? AND scratch_path != ''"
        # succeeded first, then the newest live route; a dead route's
        # skeleton is forensics, reachable through its own panel
        "   AND status IN ('succeeded', 'proposed')"
        " ORDER BY (status = 'succeeded') DESC, id DESC LIMIT 1",
        (goal_id,)).fetchone()
    if row is not None and (workspace / str(row["scratch_path"])).is_file():
        src = str(row["scratch_path"])
        sid = int(row["id"])
        state = ("winning_route" if str(row["status"]) == "succeeded"
                 else "open_route")
    draft = goal_workarea_draft(workspace, slug)
    if draft is not None and _mtime_or(draft) > _mtime_or(workspace / src):
        # same rule the run lane uses: while the draft is the fresher
        # text, the draft IS the live view
        try:
            return (draft.relative_to(workspace).as_posix(),
                    "in_flight", sid)
        except ValueError:
            pass
    return src, state, sid


def goal_detail(conn: sqlite3.Connection, problem: str,
                goal_id: int,
                workspace: "Path | None" = None) -> dict | None:
    """Goal drill-down: full row + dead-attempt forensics (most recent
    first, capped). With `workspace`, also the declaration source —
    the proof file minus its import prelude (a node IS its Lean text;
    the panel shows `name : statement := proof` as written), picked by
    `_goal_source` so a working node shows its work, not its stub."""
    g = conn.execute(
        "SELECT * FROM goals WHERE id = ? AND problem = ?",
        (goal_id, problem)).fetchone()
    if g is None:
        return None
    proof_text = None
    src = g["lean_path"]
    source_state, source_strategy_id = "own_file", None
    if workspace is not None:
        src, source_state, source_strategy_id = _goal_source(
            conn, workspace, goal_id, str(g["slug"]), str(g["lean_path"]))
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
    # subgoal names per route (owner, 2026-07-11): seven rows of
    # '1 subgoal' were indistinguishable — the panel names each route's
    # children and lights their stars on hover
    subgoals_of: dict[int, list[dict]] = {}
    for r in conn.execute(
            "SELECT ss.strategy_id AS sid, g2.id AS gid, g2.slug AS slug"
            " FROM strategy_subgoals ss"
            " JOIN strategies s ON s.id = ss.strategy_id"
            " JOIN goals g2 ON g2.id = ss.subgoal_id"
            " WHERE s.goal_id = ? ORDER BY g2.id", (goal_id,)):
        subgoals_of.setdefault(int(r["sid"]), []).append(
            {"id": int(r["gid"]), "slug": str(r["slug"])})
    strategies = [{
        "id": int(r["id"]),
        "status": str(r["status"]),
        "created_by": str(r["created_by"]),
        "subgoal_count": int(r["n"]),
        "subgoals": subgoals_of.get(int(r["id"]), []),
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
        # the file the source above was actually read from — the panel's
        # path label must name what it shows
        "source_path": str(src),
        # ...and WHAT it is: a proof, a live decomposition, an attempt
        # in flight, or the node's own file. The reader cannot tell a
        # route skeleton from a landed proof by looking at it.
        "source_state": source_state,
        "source_strategy_id": source_strategy_id,
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


def signoff_with_seal(conn: sqlite3.Connection,
                      problem: str) -> "dict | None":
    """The sign-off signature record (v27) + `seal_ok`: sha256 of the
    CURRENTLY stored review snapshot compared against the sha sealed at
    signing. False = the snapshot changed after the human signed (a
    refresh recomputed different content) — the reader must see that,
    not a seal that silently stopped meaning anything. None = never
    signed / revoked / predates signatures."""
    import hashlib
    rec = db.get_ingest_signoff(conn, problem)
    if rec is None:
        return None
    snap = db.get_review_snapshot(conn, problem)
    current_sha = (hashlib.sha256(snap[0].encode("utf-8")).hexdigest()
                   if snap else None)
    return {**rec, "seal_ok": (rec.get("snapshot_sha") is not None
                               and rec.get("snapshot_sha") == current_sha)}


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


_CTX_LINE_RE = re.compile(r"^(?:open(?:\s+scoped)?\b|universe\b|variable\b)")


def _context_preamble(text: str, first_decl_pos: int) -> str:
    """The module's context lines (`open` / `open scoped` / `universe`
    / `variable` + their indented continuations) before the first decl.
    A decl's source is NOT self-contained without them: the librarian
    hoists instance hypotheses into a `variable` block, so a probe
    that re-elaborates the bare source auto-binds `N`/`EH` as naked
    Types and every instance lookup fails (owner report, 2026-07-18:
    a wall of `failed to synthesize TopologicalSpace N` over a goal of
    sorries). Comments are stripped first so prose starting with
    "open …" inside the module docstring can't leak in."""
    head = re.sub(r"/-[\s\S]*?-/", "", text[:first_decl_pos])
    out: "list[str]" = []
    cont = False
    for ln in head.split("\n"):
        if _CTX_LINE_RE.match(ln):
            out.append(ln)
            cont = True
        elif cont and ln.strip() != "" and ln[:1] in (" ", "\t"):
            out.append(ln)
        else:
            cont = False
    return "\n".join(out).strip()


def _scan_library_file(
        text: str,
) -> "tuple[str, dict[str, tuple[int, str, str, str, str | None]], list[str], str]":
    """(module_doc, {short_decl_name: (line, docstring, kind, stmt,
    source)}, imports, context). `line` is 1-based — same domain as the
    oracle-backed `library_decls.src_line`, so the two sort keys mix
    cleanly. `source` is the decl's full source block (attributes +
    header + body, docstring excluded) — the chapter's run state seeds
    an editor with it; `context` is the preamble that makes a source
    block elaborate standalone."""
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
    context = _context_preamble(
        text, matches[0].start() if matches else len(text))
    return module_doc, docs, _IMPORT_RE.findall(text), context


#: path str -> (mtime_ns, module_doc, docs, imports, word-set, context)
#: — the _cite_file_cache pattern: stat everything, re-read only
#: changes. The chapter is polled every 30s; steady-state ~stat-only.
_chapter_scan_cache: "dict[str, tuple[int, str, dict, list[str], frozenset, str]]" = {}


def _scanned_library_file(
        workspace: Path, path: str,
) -> "tuple[str, dict[str, tuple[int, str, str, str]], list[str], frozenset, str]":
    """Mtime-memoized `_scan_library_file` plus the file's whole-word
    token set — `short in words` is equivalent to the boundary-guarded
    regex search because decl short names are single `[\\w']+` tokens."""
    fp = workspace / path
    try:
        mtime = fp.stat().st_mtime_ns
    except OSError:
        _chapter_scan_cache.pop(path, None)
        return "", {}, [], frozenset(), ""
    cached = _chapter_scan_cache.get(path)
    if cached is None or cached[0] != mtime:
        try:
            # errors="replace": presentation must never fail the page
            # (same policy as _cite_file_cache)
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:  # transient read failure — retry next request
            return "", {}, [], frozenset(), ""
        module_doc, docs, imports, context = _scan_library_file(text)
        cached = (mtime, module_doc, docs, imports,
                  frozenset(re.findall(r"[\w']+", text)), context)
        _chapter_scan_cache[path] = cached
    return cached[1], cached[2], cached[3], cached[4], cached[5]


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
        module_doc, docs, imports, _words, context = scanned[path]
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
                # the module preamble (opens + variable block) that
                # makes `source` elaborate standalone — without it the
                # probe's instance hypotheses vanish and the goal
                # collapses into sorries
                "context": context or None,
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
    # Trust colophon (design round, 2026-07-13): the chapter states its
    # own guarantees from RECORDED facts only — decl count, and the
    # axiom whitelist the bridge gate enforced (Gate B re-derives the
    # root from the Library alone and rejects any axiom outside it;
    # the migrate gate rejects sorry). Read-side; nothing here feeds
    # soundness.
    axioms: "list[str]" = []
    try:
        from ..state import manifest as _mfst
        mpath = db.problem_dir(workspace, problem) / "Manifest.md"
        axioms = (_mfst.effective_axioms(_mfst.parse(mpath), problem=problem)
                  if mpath.exists()
                  else list(_mfst.FRAMEWORK_DEFAULT_AXIOMS))
    except Exception:  # noqa: BLE001 — a colophon must never 500 the page
        axioms = []
    # The theorem itself: the problem's root statement — Gate B
    # re-derives exactly this from the Library modules alone, so it IS
    # what the chapter proves. Surfaced so the chapter can OPEN with
    # its main result (first-time QA, 2026-07-20: a mathematician
    # searched the stokes chapter and never found Stokes' theorem —
    # old harvests lost their claim flags, leaving Highlights all
    # vocabulary and keystones).
    root = None
    try:
        rrow = conn.execute(
            "SELECT slug, statement, lean_path FROM goals"
            " WHERE problem = ? AND origin = 'root'"
            " ORDER BY id LIMIT 1", (problem,)).fetchone()
        if rrow is not None:
            root = {
                "slug": str(rrow["slug"]),
                "statement": _goal_signature(
                    workspace, str(rrow["slug"]), rrow["lean_path"],
                    rrow["statement"]) or str(rrow["statement"]),
            }
    except sqlite3.OperationalError:
        pass
    return {
        "problem": problem,
        "bridged_at": rows[0]["library_bridged_at"],
        "root": root,
        "files": files,
        "colophon": {
            "decls": sum(len(f["decls"]) for f in files),
            "axioms": axioms,
        },
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
                # owner-editable display title; null = filename stands in
                "title": meta.title,
                # provenance: 'user' | 'fetched' | null (pre-provenance)
                "added_by": meta.added_by,
                "pages": meta.pages,
                "chars": meta.chars,
                "original": original,
                "has_map": _shelf.map_path(workspace, meta.id).exists(),
                "map_stale": _shelf.map_is_stale(workspace, meta.id),
                "bound": bound.get(meta.id, []),
            })
    papers.sort(key=lambda p: (p["title"] or p["source_name"]).lower())
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
