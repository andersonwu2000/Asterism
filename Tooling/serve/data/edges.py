"""Citation edges (constellation truth) + `problem_detail`, the read
side's biggest single aggregation: goal DAG, strategy edges, citation
edges, decision timeline slice, Programme summary, and the group tree
— everything one problem-detail page needs in one read.

Split out of `data.py` 2026-08-28 (Phase B, B3). The file's own
section boundary ran through `programme`/`_programme_events`/
`_programme_rev`/`_group_clause`: they moved to `timeline.py` instead
(see the package docstring for why) — this module's own calls into
them and into the groups-tree cluster (`problem_detail`'s
`programme_rev`/`programme_events`/`groups` fields, and the goal
signature / disproof-link lookups) are the only cross-module imports
`edges.py` carries.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from ...state import db
from . import _link_kind_expr
from .status import _live_daemon_pid, _refine_chip, _status_chip, _working
from .timeline import (
    _disproof_links,
    _goal_signature,
    _programme_events,
    _programme_rev,
    _top_group_id,
    groups_of,
)


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
            # a goal's birth annotation comes from the proposal that
            # MINTED it; a later route that merely cites it has its own
            # comment block for its own purposes, and whichever row the
            # scan happened to reach first was winning
            f" WHERE g.problem = ? AND {_link_kind_expr(conn)} = 'minted'",
            (problem,)):
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
    # doing"), the cockpit's run-strip data (it inherited the shape of
    # the retired demo/ stats panel, deleted 2026-08-26).
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
            "SELECT strategy_id, subgoal_id, position,"
            f" {_link_kind_expr(conn)} AS link_kind FROM strategy_subgoals"
            " ORDER BY strategy_id, position"):
        if int(e["strategy_id"]) in strat_ids:
            edges.append({
                "strategy_id": int(e["strategy_id"]),
                "subgoal_id": int(e["subgoal_id"]),
                "position": int(e["position"]),
                # v44 provenance, and the sky cannot draw the tree
                # without it: 'minted' = this strategy CREATED the
                # sub-goal (a decomposition branch), 'cited' = it
                # merely reuses one that already existed (a
                # cross-link). Flattened, seven routes reusing one
                # lemma drew seven limbs across the sky AND dragged
                # the lemma under all of them.
                "link_kind": str(e["link_kind"]),
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
        from ...quality import review as _review
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
    from ...core import config as _config
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
