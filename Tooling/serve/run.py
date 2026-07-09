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

import json
import re
import sqlite3
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    while lines and _PRELUDE_RE.match(lines[0]):
        lines.pop(0)
    while lines and _CLOSER_RE.match(lines[-1]):
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


def _scratch_drafts(workspace: Path) -> "list[tuple[str, str, float, Path]]":
    """(kind, problem, ctx_mtime, dir) for each live agent workarea
    under `.attempts/`, identified by its Context.md title line. A
    Forward worker's bricks live ONLY here until they land (no goal
    row, no lean_path — its lane looked forever idle while the LSP was
    hard at work; owner, 2026-07-09). Presentation only: a workarea
    rmtree'd mid-scan just drops out."""
    out: list[tuple[str, str, float, Path]] = []
    try:
        entries = list((workspace / ".attempts").iterdir())
    except OSError:
        return out
    for d in entries:
        if d.name.startswith("_") or not d.is_dir():
            continue
        ctx = d / "Context.md"
        try:
            with ctx.open(encoding="utf-8", errors="replace") as f:
                m = _CTX_TITLE_RE.match(f.readline())
            if m:
                out.append((m.group(1), m.group(2), ctx.stat().st_mtime, d))
        except OSError:
            continue
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


def _fetch_oauth_usage() -> "dict | None":
    """One raw call. Separated for tests (monkeypatch me)."""
    creds_path = Path.home() / ".claude" / ".credentials.json"
    token = json.loads(creds_path.read_text(encoding="utf-8"))[
        "claudeAiOauth"]["accessToken"]
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=4) as resp:
        return json.loads(resp.read())


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


def run_status(conn: sqlite3.Connection, workspace: Path,
               daemon: "dict | None") -> dict:
    d = daemon or {}
    running = bool(d.get("running"))
    scope = d.get("scope") or None
    started = d.get("started_at")

    out: dict = {
        "daemon": d,
        "problem": scope,
        "goals": None,
        "workers": [],
        "burn_run": None,
        "burn_5h": None,
        "quota": quota(),
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
    # scope when idle (the console keeps telling the last story)
    focus = scope or ((d.get("last_exit") or {}).get("scope"))
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
            lane: dict = {
                "kind": str(r["kind"]),
                "slug": r["slug"] if r["slug"] is not None else str(r["tid"]),
                "statement": r["statement"],
                "leased_at": r["leased_at"],
                "file": None,
                "path": None,
            }
            if r["lean_path"]:
                rel = str(r["lean_path"])
                lane["path"] = rel
                lane["file"] = _tail(workspace / rel)
            if lane["file"] is None:
                # no landed target file (Forward, or a goal whose file
                # isn't on disk yet) → tail the lane's scratch draft.
                # Workareas are matched by Context.md title and consumed
                # per lane (leased_at order vs workarea age), so two
                # same-kind lanes on one problem get distinct dirs.
                if drafts is None:
                    drafts = _scratch_drafts(workspace)
                match = next(
                    (t for t in drafts
                     if t[0] == lane["kind"] and t[1] == str(r["problem"])),
                    None)
                if match is not None:
                    drafts.remove(match)
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
                        lane["path"] = newest.relative_to(workspace).as_posix()
                        lane["file"] = _tail(newest)
            out["workers"].append(lane)
    return out


def register(app, workspace: Path, ro) -> None:  # noqa: ANN001 — FastAPI app
    """Mount GET /api/run. `ro` is app.py's `_ro` contextmanager —
    borrowed so this module inherits the same 404/503 semantics."""

    @app.get("/api/run")
    def run() -> dict:
        from ..core.cli import daemon_status
        d = daemon_status(workspace)
        if not (workspace / "asterism.db").exists():
            return {"daemon": d, "problem": None, "goals": None,
                    "workers": [], "burn_run": None, "burn_5h": None,
                    "quota": quota(), "recent": []}
        with ro(workspace) as conn:
            return run_status(conn, workspace, d)
