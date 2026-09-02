"""GET /api/run — mission control's one read.

"What is the machine doing RIGHT NOW": daemon liveness + the scoped
problem's goal tallies, one lane per live worker (unit, statement, and
a tail of the file it is writing — spawn writes go through to the real
path, so the goal's lean file IS the live view), burn for this run and
for the trailing 5h (the subscription-window proxy: true plan quotas
are not queryable, so the UI shows spend against the window instead of
pretending to know the ceiling), and the recent decision feed.

Read-only aggregation in the data.py mold: fresh read-only connection
per request, never touches the gateway, never writes. Lives in its own
module (not data.py) so the run surface can evolve without churning
the shared aggregation file.
"""
from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core import usage_quota
from ..state import db
from . import data as _data

#: sanity clip for a runaway file — proof files are a few KB, and the
#: card scrolls, so this is a guard, not a window
_TAIL_BYTES = 32768

#: the file header: imports, opens, namespace/section machinery. The
#: card shows the MATHEMATICS (owner: 12 lines was too little — strip
#: the prelude and the trailing `end` closers, show everything else;
#: the Files tab still reads the raw file)
_PRELUDE_RE = re.compile(
    r"^\s*(?:import\s|open[\s(]|namespace\s|set_option\s"
    r"|section\b|noncomputable section\b)|^\s*$")
_CLOSER_RE = re.compile(r"^\s*end\b|^\s*$")


def _tail(path: Path) -> "dict | None":
    """The live body of a file being written — whole text minus the
    prelude and the closing `end`s. None = no file yet (a worker that
    has not touched disk is still warming up its prompt — that is
    itself information)."""
    try:
        st = path.stat()
        with open(path, "rb") as f:
            if st.st_size > _TAIL_BYTES:
                f.seek(-_TAIL_BYTES, 2)
            raw = f.read()
    except OSError:
        return None
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if st.st_size > _TAIL_BYTES and len(lines) > 1:
        lines = lines[1:]  # first line is almost surely cut mid-way
    # prelude/`end` stripping is LEAN grammar — applied to a markdown
    # plan note it ate lines like "end state: …" (self-audit,
    # 2026-07-14); non-.lean files only lose blank edges
    if path.suffix == ".lean":
        while lines and _PRELUDE_RE.match(lines[0]):
            lines.pop(0)
        while lines and _CLOSER_RE.match(lines[-1]):
            lines.pop()
    else:
        while lines and lines[0].strip() == "":
            lines.pop(0)
        while lines and lines[-1].strip() == "":
            lines.pop()
    quiet = max(0.0, datetime.now(timezone.utc).timestamp() - st.st_mtime)
    return {
        "tail": "\n".join(lines),
        "size": int(st.st_size),
        "quiet_sec": int(quiet),
    }


#: Context.md title — every agent workarea opens with
#: '# <Kind> context — <problem>' (agent/context.py)
_CTX_TITLE_RE = re.compile(r"#\s*(\w+) context — (.+?)\s*$")
#: the strategist Context.md's `## Trigger` line (phase2_context)
_TRIGGER_RE = re.compile(r"`trigger_kind`:\s*(\w+)")


#: the live in-flight draft for a goal — shared with the goal panel,
#: which shows the same freshest text (state/data.py owns it)
_goal_workarea_draft = _data.goal_workarea_draft


def _pick_group_workarea(conn: sqlite3.Connection, cands: list,
                         group: dict) -> "tuple | None":
    """Which of several same-problem Strategist workareas belongs to
    THIS group (v35).

    A sub-group's context compile stages `charter.md` — the same bytes
    the judge reads — so the charter identifies the workarea; the top
    group stages none. Sibling groups run concurrently by design, and
    without this the lanes would swap thinking with each other. Falls
    back to the first candidate: a wake caught between mkdir and the
    charter write is better shown against its problem than not at all.
    """
    if not cands:
        return None
    want = ""
    if not group.get("is_top"):
        try:
            from ..state import groups as _groups
            want = _groups.charter_digest(conn, str(group["problem"]),
                                          int(group["id"]))
        except (sqlite3.OperationalError, KeyError, ValueError):
            want = ""
    for t in cands:
        try:
            text = (t[3] / "charter.md").read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text.strip() == want.strip():
            return t
    return cands[0]


def _pipeline_kind_problem(conn, pipeline_id: str) -> "tuple[str, str] | None":
    """(kind, problem) for a dispatched pipeline, from the DB — the
    structured signal (`.attempts/<dir>` IS the pipeline id, and every
    dispatch has a `pipelines` row since v38)."""
    try:
        row = conn.execute(
            "SELECT kind, target_kind, target_id FROM pipelines"
            " WHERE id = ?", (pipeline_id,)).fetchone()
        if row is None:
            return None
        tk, tid = str(row["target_kind"]), str(row["target_id"])
        if tk == "Problem":
            return str(row["kind"]), tid
        q = {"Goal": "SELECT problem FROM goals WHERE id = ?",
             "Group": "SELECT problem FROM groups WHERE id = ?",
             "Strategy": "SELECT g.problem FROM strategies s"
                         " JOIN goals g ON g.id = s.goal_id"
                         " WHERE s.id = ?"}.get(tk)
        if q is None:
            return None
        p = conn.execute(q, (tid,)).fetchone()
        return (str(row["kind"]), str(p["problem"])) if p else None
    except sqlite3.OperationalError:
        return None


def _scratch_drafts(conn, workspace: Path) -> "list[tuple[str, str, float, Path, str]]":
    """(kind, problem, ctx_mtime, dir, stage) for each live agent
    workarea under `.attempts/`. A Forward worker's bricks live ONLY
    here until they land (no goal row, no lean_path — its lane looked
    forever idle while the LSP was hard at work; owner, 2026-07-09).
    Presentation only: a workarea rmtree'd mid-scan just drops out.

    Identified by the DB (dir name = pipeline id), NOT the Context.md
    title: the title-regex era ended 2026-08-26 when the worker header
    became `# <problem> — BRIEF` and every mint/direct workarea went
    silently invisible to the lanes (the frontend's card fell back to
    static copy) — free text is not a signal, the pipelines table is.
    The title regex stays as fallback for dirs the DB does not know.
    """
    out: list[tuple[str, str, float, Path, str]] = []
    try:
        entries = list((workspace / ".attempts").iterdir())
    except OSError:
        return out
    for d in entries:
        if d.name.startswith("_") or not d.is_dir():
            continue
        ctx = d / "Context.md"
        try:
            mtime = ctx.stat().st_mtime
        except OSError:
            continue
        kp = _pipeline_kind_problem(conn, d.name)
        if kp is None:
            try:
                with ctx.open(encoding="utf-8", errors="replace") as f:
                    m = _CTX_TITLE_RE.match(f.readline())
            except OSError:
                continue
            if m is None:
                continue
            kp = (m.group(1), m.group(2))
        out.append((kp[0], kp[1], mtime, d, ""))
    out.sort(key=lambda t: t[2])
    return out


# ---------------------------------------------------------------------
# Subscription quota — the REAL windows, not a proxy. Claude Code's
# login leaves an OAuth token at ~/.claude/.credentials.json; the same
# endpoint its statusline uses (api.anthropic.com/api/oauth/usage)
# reports five_hour / seven_day utilization and per-model scoped
# limits. Read-only against the user's own account; the token never
# appears in any response or log. Memoized 60s (failures 30s) — the
# console polls every 2s and the endpoint 429s eagerly.
# ---------------------------------------------------------------------

_quota_memo: "dict[str, object]" = {
    "at": 0.0, "value": None, "ttl": 0.0, "last_good": None}


def reset_quota_memo() -> None:
    """Flush the meters (account switch: the old account's numbers
    must not linger for the memo's lifetime)."""
    _quota_memo.update(at=0.0, value=None, ttl=0.0, last_good=None)
    _log_quota_memo.update(at=0.0, value=[])


#: The OTHER kind of meter: providers with no endpoint to ask, read back
#: off the ledger they wrote themselves (`usage_from_session_log`).
#: Memoized harder than claude's — the reading only changes when a spawn
#: finishes a turn, and finding it walks the preserved rollouts.
_log_quota_memo: "dict[str, object]" = {"at": 0.0, "value": []}


def log_quota(workspace: "Path | str") -> "list[dict]":
    """Session-log meters, in the console's wire shape (epochs become
    ISO, as the endpoint's already are).

    Every entry carries `measured_at`, and the console is required to
    show it: this is the last reading a spawn left behind, not a live
    one, and the two are the same number with different meanings."""
    now = time.monotonic()
    if now - float(_log_quota_memo["at"]) < 45.0:  # type: ignore[arg-type]
        return _log_quota_memo["value"]  # type: ignore[return-value]
    rows: "list[dict]" = []
    try:
        for row in usage_quota.session_log_usage(workspace):
            rows.append({
                "provider": row["provider"],
                "plan": row.get("plan"),
                "reached": row.get("reached"),
                "measured_at": _iso(row.get("measured_at")),
                "windows": [{"minutes": w.get("minutes"),
                             "utilization": w.get("utilization"),
                             "resets_at": _iso(w.get("resets_at"))}
                            for w in row.get("windows") or []],
            })
    except Exception:  # noqa: BLE001 — a meter is garnish, never a failure
        rows = []
    _log_quota_memo.update(at=now, value=rows)
    return rows


def _iso(epoch: "object") -> "str | None":
    if not isinstance(epoch, (int, float)):
        return None
    return datetime.fromtimestamp(float(epoch), timezone.utc).isoformat()


def _fetch_oauth_usage() -> "dict | None":
    """One raw call. Separated for tests (monkeypatch me). Body lives
    in core/usage_quota so the dispatcher's quota-wait probes the same
    endpoint through the same code path."""
    return usage_quota.fetch_usage()


def quota() -> "dict | None":
    """{five_hour, seven_day, scoped[]} or None (no login file, expired
    token, rate-limited, offline — the console simply omits the meter)."""
    now = time.monotonic()
    if now - float(_quota_memo["at"]) < float(_quota_memo["ttl"]):  # type: ignore[arg-type]
        return _quota_memo["value"]  # type: ignore[return-value]
    value = None
    try:
        raw = _fetch_oauth_usage()
        if raw is not None:
            def window(node: "dict | None") -> "dict | None":
                if not node or node.get("utilization") is None:
                    return None
                return {"utilization": float(node["utilization"]),
                        "resets_at": node.get("resets_at")}
            scoped = []
            for lim in raw.get("limits") or []:
                scope = lim.get("scope") or {}
                model = (scope.get("model") or {}).get("display_name")
                if lim.get("kind") == "weekly_scoped" and model:
                    scoped.append({
                        "name": str(model),
                        "percent": float(lim.get("percent") or 0),
                        "resets_at": lim.get("resets_at"),
                        "is_active": bool(lim.get("is_active")),
                    })
            value = {"five_hour": window(raw.get("five_hour")),
                     "seven_day": window(raw.get("seven_day")),
                     "scoped": scoped}
    except Exception:  # noqa: BLE001 — quota is garnish, never a failure
        value = None
    if value is not None:
        _quota_memo.update(at=now, value=value, ttl=120.0, last_good=value)
    else:
        # stale-while-error: a 429/offline blip keeps the last good
        # reading on the meter instead of blanking it
        _quota_memo.update(at=now, value=_quota_memo["last_good"], ttl=60.0)
    return _quota_memo["value"]  # type: ignore[return-value]


def _proposal_cycle(workarea: Path) -> "dict | None":
    """The strategist wake's proposal↔Adversary cycle, read from its
    working files (research_mode_design §2-§3; display-only). Phases:
    `proposing` (drafting, no round yet) → `judging` (round dir exists,
    no readable verdict) → `revising` (rebut; the fired criteria ride
    along as objections) → `passed`. The ruling itself comes from
    `adversary.parse_verdict` — the contract's owner — so a change to
    the verdict file cannot drift this reader. `_tail_path` names the
    live text of the phase — the draft while the strategist speaks, the
    on-trial proposal while the judge deliberates."""
    proposal = workarea / "proposal.md"
    rounds: "list[tuple[int, Path]]" = []
    adv = workarea / "adversary"
    if adv.is_dir():
        try:
            for p in adv.iterdir():
                if p.is_dir() and re.fullmatch(r"r\d+", p.name):
                    rounds.append((int(p.name[1:]), p))
        except OSError:
            pass
        rounds.sort()
    if not rounds and not proposal.is_file():
        return None

    def _mtime(p: Path) -> "float | None":
        try:
            return p.stat().st_mtime
        except OSError:
            return None

    def _since(m: "float | None") -> "int | None":
        return max(0, int(time.time() - m)) if m is not None else None

    if not rounds:
        return {"phase": "proposing", "round": 0, "objections": [],
                "since_sec": _since(_mtime(proposal)),
                "_tail_path": str(proposal)}
    n, rdir = rounds[-1]
    verdict_p = rdir / "verdict.json"
    # The ruling is READ THROUGH the contract's own parser, never
    # re-implemented here: verdict.json became a per-criterion
    # adjudication (44ff4321) and this reader's private copy of the old
    # shape silently reported every rebut as `passed` with zero
    # objections — a lying console, not just a missing fold.
    from ..pipeline.adversary import parse_verdict
    v = None
    if verdict_p.is_file():
        try:
            v, _err = parse_verdict(verdict_p.read_text(encoding="utf-8"))
        except OSError:
            v = None
    if v is None:
        # no verdict yet, half-written, or one the framework refuses —
        # in every case the judge is still out (a rejected verdict makes
        # the pipeline re-spawn it), so `judging` is the honest phase
        return {"phase": "judging", "round": n, "objections": [],
                "since_sec": _since(_mtime(rdir / "proposal.md")
                                    or _mtime(rdir)),
                "_tail_path": str(rdir / "proposal.md")}
    if v.get("verdict") == "rebut":
        return {"phase": "revising", "round": n,
                "objections": [str(c) for c in
                               (v.get("criticisms") or [])][:6],
                "since_sec": _since(_mtime(verdict_p)),
                "_tail_path": str(proposal if proposal.is_file()
                                  else rdir / "proposal.md")}
    return {"phase": "passed", "round": n, "objections": [],
            "since_sec": _since(_mtime(verdict_p)),
            "_tail_path": str(rdir / "proposal.md")}


#: The run log is a live poll, not an archive read: bound BOTH sides of
#: the merge. A pattern scope can hold a dozen problems and stokes alone
#: yields 1148 events, so an unbounded merge would ship megabytes every
#: few seconds. The problem page carries the whole archive per problem,
#: which is where the console points when it truncates.
_RUN_EVENT_PROBLEMS = 8
_RUN_EVENT_CAP = 400


def _resolve_focus(conn: sqlite3.Connection, scope: "str | None",
                   live_pid: "int | None",
                   override: "str | None") -> "tuple[str | None, list[str]]":
    """(focus, candidates). A pattern scope (`PutnamCmp.%`) runs
    several problems in one daemon — the console's lens must land on
    REAL problem names, not the raw pattern (which 404'd the detail
    fetch and blanked the sky; owner report, 2026-07-19). Candidates:
    live-leased problems first (most recent lease first), then other
    pattern matches by recency; `override` is the UI's picker choice."""
    candidates: "list[str]" = []
    if live_pid is not None:
        for r in conn.execute(
                "SELECT problem, MAX(leased_at) AS m FROM queue"
                " WHERE owner_pid = ? AND problem IS NOT NULL"
                " GROUP BY problem ORDER BY m DESC", (live_pid,)):
            candidates.append(str(r["problem"]))
    if scope:
        # A scope names several problems in two ways now: a LIKE pattern,
        # or the explicit `a,b,c` list a multi-problem run starts with
        # (HID §1.4). Both expand to the lens's candidate list.
        _names = db.scope_names(scope)
        if _names is not None:
            for name in _names:
                if name not in candidates:
                    candidates.append(name)
        elif "%" in scope:
            for r in conn.execute(
                    "SELECT name FROM problems WHERE name LIKE ?"
                    " ORDER BY last_strategist_at IS NULL,"
                    " last_strategist_at DESC LIMIT 12", (scope,)):
                if str(r["name"]) not in candidates:
                    candidates.append(str(r["name"]))
        elif scope not in candidates:
            candidates.append(scope)
    if override and override in candidates:
        return override, candidates
    return (candidates[0] if candidates else None), candidates


def run_status(conn: sqlite3.Connection, workspace: Path,
               daemon: "dict | None",
               focus_override: "str | None" = None) -> dict:
    d = daemon or {}
    running = bool(d.get("running"))
    scope = d.get("scope") or None
    started = d.get("started_at")

    out: dict = {
        "daemon": d,
        "problem": scope,
        "problems": [],
        "goals": None,
        "workers": [],
        "burn_run": None,
        "burn_5h": None,
        "quota": quota(),
        "quota_logged": log_quota(workspace),
        "recent": [],
    }

    # burn: the trailing-5h window is always worth knowing (idle spend
    # counts against the same subscription window); this-run only
    # exists while a run does
    five_h_ago = (datetime.now(timezone.utc)
                  - timedelta(hours=5)).isoformat()
    out["burn_5h"] = _data.telemetry_usage(conn, since=five_h_ago)
    if running and started:
        out["burn_run"] = _data.telemetry_usage(conn, since=str(started))

    # the problem under the lens: the live scope, or the last run's
    # scope when idle (the console keeps telling the last story) —
    # resolved through pattern scopes to a real problem name
    live_pid_early = _data._live_daemon_pid(d)
    raw_focus = scope or ((d.get("last_exit") or {}).get("scope"))
    focus, out["problems"] = _resolve_focus(
        conn, raw_focus, live_pid_early, focus_override)
    if focus:
        counts: dict[str, int] = {}
        for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM goals"
                " WHERE problem = ? GROUP BY status", (focus,)):
            counts[str(r["status"])] = int(r["n"])
        if counts:
            out["goals"] = {
                "open": counts.get("open", 0),
                "attempting": counts.get("attempting", 0),
                "proved": counts.get("proved", 0),
                "total": sum(counts.values()),
            }
        out["problem"] = focus
        for r in conn.execute(
                "SELECT decision_kind, outcome, updated_at"
                " FROM strategist_decisions"
                " WHERE problem = ? AND outcome IS NOT NULL"
                " ORDER BY updated_at DESC LIMIT 8", (focus,)):
            out["recent"].append({
                "kind": str(r["decision_kind"]),
                "outcome": str(r["outcome"]),
                "at": str(r["updated_at"]),
            })

    # worker lanes — queue leases owned by the LIVE pid only (same
    # gate as the board: a dead owner's lease is residue, not work)
    live_pid = _data._live_daemon_pid(d)
    if live_pid is not None:
        drafts: "list[tuple[str, str, float, Path]] | None" = None
        for r in conn.execute(
                "SELECT q.kind AS kind, q.target_kind AS tk,"
                " q.target_id AS tid, q.leased_at AS leased_at,"
                " q.problem AS problem,"
                " g.slug AS slug, g.statement AS statement,"
                " g.lean_path AS lean_path"
                " FROM queue q LEFT JOIN goals g ON q.target_kind = 'Goal'"
                " AND g.id = CAST(q.target_id AS INTEGER)"
                " WHERE q.owner_pid = ? ORDER BY q.leased_at", (live_pid,)):
            # binders+conclusion for the card (statement stores the
            # bare conclusion; same chokepoint as problem_detail)
            sig = _data._goal_signature(
                workspace, str(r["slug"] or ""), r["lean_path"],
                r["statement"]) if r["slug"] is not None else None
            # v35 — a Strategist seat belongs to a GROUP, so its
            # target_id is a group id: without this the lane's identity
            # line read as a bare number where the problem name used to
            # be (live, sylvester_gallai 2026-08-02)
            group = (_data.group_card(conn, int(r["tid"]))
                     if str(r["tk"]) == "Group" and str(r["tid"]).isdigit()
                     else None)
            lane: dict = {
                "kind": str(r["kind"]),
                "slug": (r["slug"] if r["slug"] is not None
                         else (group or {}).get("problem")
                         or str(r["tid"])),
                # the discussion group this agent speaks for (null = not
                # a group seat). A sub-group's charter is its subject.
                "group": group,
                # which problem this agent is on — a pattern scope runs
                # several at once and the cards were ambiguous
                "problem": str(r["problem"]) if r["problem"] else None,
                "statement": sig if sig is not None else r["statement"],
                "leased_at": r["leased_at"],
                "file": None,
                "path": None,
                # Strategist only: WHY it woke (trigger_kind from its
                # Context.md) — 'reviewing results' vs 'routine look'
                "mode": None,
                # Retained as a null: the wake-split stage it named is
                # gone (2026-08-11) and the field stays so a stale UI
                # bundle reads "no stage" rather than KeyError.
                "stage": None,
            }
            if r["lean_path"]:
                rel = str(r["lean_path"])
                lane["path"] = rel
                lane["file"] = _tail(workspace / rel)
                # A Formalizer ATTEMPT drafts patch.lean in its
                # workarea and lands only at commit — the goal's own
                # file is a static sorry stub the whole while (owner:
                # "the card was sorry start to end, then subgoals
                # appeared"). While the draft is the fresher text, the
                # draft IS the live view.
                if r["slug"]:
                    draft = _goal_workarea_draft(workspace, str(r["slug"]))
                    if draft is not None:
                        try:
                            landed_m = (workspace / rel).stat().st_mtime
                        except OSError:
                            landed_m = -1.0
                        try:
                            if draft.stat().st_mtime > landed_m:
                                dtail = _tail(draft)
                                if dtail is not None:
                                    lane["path"] = draft.relative_to(
                                        workspace).as_posix()
                                    lane["file"] = dtail
                        except OSError:
                            pass
            if lane["file"] is None:
                # no landed target file (Forward, or a goal whose file
                # isn't on disk yet) → tail the lane's scratch draft.
                # Workareas are matched by Context.md title and consumed
                # per lane (leased_at order vs workarea age), so two
                # same-kind lanes on one problem get distinct dirs.
                if drafts is None:
                    drafts = _scratch_drafts(conn, workspace)
                cands = [t for t in drafts
                         if t[0] == lane["kind"]
                         and t[1] == str(r["problem"])]
                # v35 — sibling groups run concurrently, so one problem
                # can have two Strategist workareas at once and "first
                # match wins" would show each lane the other's thinking.
                # The context compiler stages `charter.md` for a
                # sub-group (and none for the top group), so the charter
                # identifies the workarea exactly.
                match = _pick_group_workarea(conn, cands, group) \
                    if group is not None else (cands[0] if cands else None)
                if match is not None:
                    drafts.remove(match)
                    # the Strategist's Context.md already names WHY it woke
                    # (`## Trigger` → trigger_kind) — surface it so the lane
                    # says which mode this think is, not just "thinking"
                    # (owner, 2026-07-12). Read-side only, like the title.
                    if lane["kind"] == "Strategist":
                        try:
                            head = (match[3] / "Context.md").read_text(
                                encoding="utf-8", errors="replace")[:4000]
                            mm = _TRIGGER_RE.search(head)
                            if mm:
                                lane["mode"] = mm.group(1)
                        except OSError:
                            pass
                        # what it's THINKING: the agent drafts its plan
                        # note (_plan.md) incrementally in the workarea —
                        # tail it live; before the first write, the
                        # problem's standing plan (being revised) stands
                        # in. The page went dead at its most alive
                        # moment (owner-approved design round K).
                        for cand in (
                                match[3] / "_plan.md",
                                db.problem_dir(workspace, str(r["problem"]))
                                / ".drafts" / "strategist_plan.md"):
                            if cand.is_file():
                                ptail = _tail(cand)
                                if ptail is not None:
                                    lane["path"] = cand.relative_to(
                                        workspace).as_posix()
                                    lane["file"] = ptail
                                    break
                        # research mode: the proposal↔Adversary argument
                        # happens in FILES (proposal.md, adversary/r<N>/
                        # verdict.json) and the plan note may not move at
                        # all — narrate the cycle instead of half an hour
                        # of silence (owner, 2026-07-18)
                        cyc = _proposal_cycle(match[3])
                        if cyc is not None:
                            tail_path = cyc.pop("_tail_path", None)
                            lane["cycle"] = cyc
                            if tail_path is not None:
                                cand = Path(tail_path)
                                ptail = _tail(cand)
                                if ptail is not None:
                                    lane["path"] = cand.relative_to(
                                        workspace).as_posix()
                                    lane["file"] = ptail
                    if lane["file"] is None:
                        newest: "Path | None" = None
                        newest_m = -1.0
                        try:
                            for f in match[3].glob("*.lean"):
                                if f.name.startswith("_"):
                                    continue  # probe/audit helpers, not drafts
                                mt = f.stat().st_mtime
                                if mt > newest_m:
                                    newest_m = mt
                                    newest = f
                        except OSError:
                            newest = None
                        if newest is not None:
                            lane["path"] = newest.relative_to(
                                workspace).as_posix()
                            lane["file"] = _tail(newest)
            out["workers"].append(lane)
    return out


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount GET /api/run. `ro` is app.py's `_ro` contextmanager —
    borrowed so this module inherits the same 404/503 semantics."""

    @app.get("/api/run")
    def run(problem: "str | None" = None) -> dict:
        """`problem` = the UI's lens pick when a pattern scope runs
        several problems at once (ignored unless it's a live
        candidate)."""
        from ..core.cli import daemon_status
        d = daemon_status(workspace)
        if not (workspace / "asterism.db").exists():
            return {"daemon": d, "problem": None, "problems": [],
                    "goals": None, "workers": [], "burn_run": None,
                    "burn_5h": None, "quota": quota(),
                    "quota_logged": log_quota(workspace),
                    "recent": []}
        with ro(workspace) as conn:
            return run_status(conn, workspace, d, focus_override=problem)

    @app.get("/api/run/events")
    def run_events(problem: "str | None" = None) -> dict:
        """The Timeline, run-flavoured — the same log the problem page
        reads, across every problem under the run's lens.

        Two framings of one renderer, the shape `419dcb31` settled when
        the Programme joined this page: the problem page keeps the
        ARCHIVE (one problem, all of it, lenses and follow), and the
        Engine reads what is happening on the run you are sitting on.
        The console cannot delegate this to the problem page — a
        pattern scope runs several problems at once and the problem
        page can only ever show one.

        Scope resolution is `_resolve_focus`, the same call `/api/run`
        makes, so the slots and the log can never disagree about which
        run they are describing.
        """
        from ..core.cli import daemon_status
        d = daemon_status(workspace)
        if not (workspace / "asterism.db").exists():
            return {"events": [], "log_since": None, "groups": [],
                    "problems": [], "truncated": 0}
        with ro(workspace) as conn:
            raw = (d.get("scope")
                   or ((d.get("last_exit") or {}).get("scope")))
            focus, names = _resolve_focus(
                conn, raw, _data._live_daemon_pid(d), problem)
            if focus and focus not in names:
                names = [focus, *names]
            events: "list[dict]" = []
            groups: "list[dict]" = []
            since: "str | None" = None
            for name in names[:_RUN_EVENT_PROBLEMS]:
                one = _data.problem_events(conn, name)
                for e in one["events"]:
                    e["problem"] = name
                events.extend(one["events"])
                groups.extend(one["groups"])
                since = one["log_since"]
            # The seam is a per-problem fact ("the engine started
            # recording HERE"); with several problems merged there is
            # no single line to draw, so the run view draws none and
            # the rows keep their own `~` marks.
            if len(names) != 1:
                since = None
            events.sort(key=lambda e: e["at"], reverse=True)
            return {
                "events": events[:_RUN_EVENT_CAP],
                "truncated": max(0, len(events) - _RUN_EVENT_CAP),
                "log_since": since, "groups": groups,
                "problems": names,
            }
