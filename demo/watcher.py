"""Demo layout watcher — feeds VS Code panes during a live framework run.

The goal is visual density, not readability. Four worker panes track the
four most-recently-active spawn sandboxes; a TREE pane mirrors the
current problem's cascade structure; a stats pane shows live counters.

VS Code is configured (manually, once) with six fixed panes pointing at
the files this script writes:

    demo/active/worker_1.lean    demo/active/tree.md       demo/active/worker_2.lean
    demo/active/worker_3.lean    demo/active/stats.md      demo/active/worker_4.lean

Each pane has auto-revert enabled (Settings → Files: Auto Save = afterDelay
+ Editor: Auto Reveal). VS Code refreshes on disk change; this script
just keeps disk content fresh.

Usage during a demo run:

    python demo/watcher.py --problem sl2_v_n_irreducible

Stop with Ctrl+C; the active/ files remain on disk so VS Code panes don't
flash empty.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
ACTIVE_DIR = WS / "demo" / "active"
ATTEMPTS_DIR = WS / ".attempts"
DB_PATH = WS / "asterism.db"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Spawn-kind detection runs off `Context.md` (compiled by
# `Tooling/agent/{context,phase2_context}.py` at spawn cold-start),
# not the `pipelines` table — that table is INSERT'd only at spawn
# finish (db.record_pipeline docstring: "Live state... never persisted
# to DB"), so a DB-based lookup never resolves while a spawn is alive.
# Context.md exists from the first cold-start moment and carries the
# slug + signature sections used to disambiguate kind below.
_RE_CONTEXT_GOAL = re.compile(r"^# Context for goal (\S+)")
_RE_STRATEGIST_CTX = re.compile(r"^# Strategist context — (\S+)")
_RE_FORWARD_CTX = re.compile(r"^# Forward context — (\S+)")
# Librarian Context.md header: `# Librarian — <work_kind> — <problem>`
# (compile_librarian_context). Without this the librarian work-kinds fall
# through to the ("spawning", "?") placeholder.
_RE_LIBRARIAN_CTX = re.compile(r"^# Librarian — (\w+) — (\S+)")
# A `.attempts/<uuid>/` path inside a process command line — the daemon spawns
# one claude subprocess per in-flight pipeline with that spawn dir on its
# argv (e.g. the Context.md / _mcp_config.json path), so a live process whose
# argv carries the uuid is ground-truth pool occupancy.
_RE_ATTEMPTS_UUID = re.compile(
    r"[\\/]\.attempts[\\/]"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})")
# Migrate Context.md also carries `## Migrate file `<path>`` — surface the
# file basename in the pipeline label so stats reads "migrate <File>.lean".
_RE_LIBRARIAN_MIGRATE_FILE = re.compile(r"^## Migrate file `([^`]+)`")
_RE_STRATEGY_NAMING = re.compile(r"^## Strategy naming\b")
# Cleanup sub-agent Context.md headers. Unlike migrate (whose top-level spawn
# carries `# Librarian — <kind> —`), the cleanup stage spawns one sub-agent per
# (file, operation), each writing its own `# <Title> — <problem>[ — `<file>`]`
# header. Map the title → a short `cleanup:<stage>` label so stats.md shows which
# stage each worker is on instead of the ("spawning", "?") placeholder.
_CLEANUP_TITLES = {
    "dedup audit": "cleanup:dedup",
    "dedup bridge": "cleanup:bridge",
    "Proof-simplification triage": "cleanup:simp-mark",
    "Simplify one proof": "cleanup:simplify",
    "Variable extraction": "cleanup:variables",
    "Docstring polish": "cleanup:docstring",
}
_RE_CLEANUP_CTX = re.compile(r"^# (.+?) — (\S.*?)(?: — `([^`]+)`)?\s*$")
_RE_CLEANUP_FILE = re.compile(r"^# file: (\S+)")  # dedup audit's file is line 2

# Spawns whose dir contained any file touched in the last ACTIVE_WINDOW
# seconds are treated as "live". Set to match the framework's
# `spawn_timeout_sec` (default 900s = 15min) — an agent in mid-thought
# can go silent (no file writes between initial Context.md and final
# patch.lean / decision.json) for several minutes, and a tighter
# window would drop the spawn from the active list while the worker
# is still genuinely running. Past spawn_timeout, the daemon would
# have killed the worker, so any spawn dir older than that has either
# wound down or been left behind by a crash.
ACTIVE_WINDOW = 900.0


def _spawn_score(pdir: Path) -> float:
    """Most recent mtime of any file under `<pdir>/`, or -inf if the
    dir is unreachable / empty. Used to pick currently-active spawns.

    Looks at any file (not just `.lean`) so Strategist spawns — which
    write `Context.md` + `decision.json` but no `.lean` — appear in
    the active set. Without this, stats.md would silently hide
    Strategist invocations and the "active pipelines (N/pool)" header
    would underreport pool occupancy.

    Framework writes `patch.lean` / `new_*.lean` / `Context.md` /
    `decision.json` directly inside `.attempts/<uuid>/` (flat layout);
    earlier framework versions used `<uuid>/sandbox/` — `rglob`
    covers both transparently.
    """
    latest = float("-inf")
    try:
        for f in pdir.rglob("*"):
            if not f.is_file():
                continue
            try:
                t = f.stat().st_mtime
            except OSError:
                continue
            if t > latest:
                latest = t
    except OSError:
        return float("-inf")
    return latest


def _session_open(pdir: Path) -> "bool | None":
    """Whether the spawn (or any of its per-decl subdirs) still holds an
    OPEN gateway session, read from `_mcp.jsonl` (the gateway logs
    `session_registered` / `session_released` there). Returns:
      - True  — a session's last event is `session_registered` → genuinely live;
      - False — every session has been `session_released` → the spawn FINISHED,
                even if its files were touched within ACTIVE_WINDOW (the
                lingering-dir over-count: a driver that doesn't rmtree finished
                dirs, e.g. the e2e driver, otherwise shows them as live);
      - None  — no `_mcp.jsonl` yet → cold-starting before the first register
                (caller keeps it via the mtime window so a just-started spawn
                isn't dropped before it registers).
    Read-only; tolerates partial / locked files mid-write."""
    found = False
    open_any = False
    try:
        mcps = list(pdir.rglob("_mcp.jsonl"))
    except OSError:
        return None
    for mcp in mcps:
        last: str | None = None
        try:
            with open(mcp, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"session_registered"' in line:
                        last = "reg"
                    elif '"session_released"' in line:
                        last = "rel"
        except OSError:
            continue
        if last is not None:
            found = True
            if last == "reg":
                open_any = True
    if not found:
        return None
    return open_any


def _pool_size() -> int:
    """Resolve dispatch.pool from Asterism.yaml, falling back to 4
    (the framework default). Read directly rather than via
    Tooling.core.config so the watcher stays standalone (no PYTHONPATH
    setup) — the daemon and watcher just have to agree on the value,
    not share the resolver. Reads once per daemon-run via caller."""
    cfg = WS / "Asterism.yaml"
    if not cfg.exists():
        return 4
    try:
        import yaml  # PyYAML is already an Asterism dep (Manifest parser)
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    except Exception:
        return 4
    if not isinstance(data, dict):
        return 4
    dispatch = data.get("dispatch")
    if not isinstance(dispatch, dict):
        return 4
    v = dispatch.get("pool")
    try:
        return int(v) if v is not None else 4
    except (TypeError, ValueError):
        return 4


# ---------------------------------------------------------------------
# Token usage aggregation (non-invasive)
#
# Claude CLI persists every spawn's transcript to
# `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`. Each `assistant`-
# typed message embeds a `usage` block: input_tokens / output_tokens /
# cache_creation_input_tokens / cache_read_input_tokens. We tail those
# JSONLs (offset-cached across ticks so steady-state work is O(new bytes
# per file)), classify each by the first `user` message's "You are running
# a <kind> task" header (set by `Tooling.llm.claude_cli`), and aggregate
# usage by (kind, model) for every message whose ISO timestamp is past
# the watcher's start time.
#
# Limitations: reflection / postmortem spawns use `--resume <sid>` so they
# append into the parent spawn's JSONL. The kind classifier is set on the
# FIRST user message, so reflection cost is folded into the parent kind
# rather than surfaced separately — accepted by design (precise split would
# need per-message inspection + a second classifier pass).
# ---------------------------------------------------------------------

_KIND_RE = re.compile(r"^You are running a (\w+) task")
# Inline-prompt paths used by `Tooling/pipeline/_retry.py` after the
# watchdog kills a stuck-thinking session. Two stages, both surfaced
# as the `rescue` kind so total framework retry overhead is visible
# separately from main pipeline spawns:
#   * stage 2 takeover (`_rescue_prompt`): fresh sid re-runs the
#     original task from the broken session's log.
#   * stage 3 postmortem (`_checkpoint_prompt`): if stage 2 also
#     deadlocks, a fresh sid writes a `_progress.md` checkpoint so
#     the next regular spawn has context to resume from.
_RESCUE_RE = re.compile(
    r"^(The previous session was killed mid-think"
    r"|You are a fresh session brought in only to write a checkpoint)"
)

# Persistent per-file state. Survives across watcher ticks so we only
# parse the new bytes appended since the last read. Cleared if watcher
# restarts (in-memory only).
_token_state: dict[Path, dict] = {}


def _daemon_start_time() -> float | None:
    """Returns the active daemon's start epoch by reading
    `.asterism/daemon.pid` mtime (singleton-lock file created at the
    top of `dispatcher.run`). Returns None if no daemon is running.

    Used as `since_ts` for token aggregation so the displayed totals
    are cumulative since the CURRENT daemon's start — surviving
    watcher restarts (state re-derived from JSONLs filtered by
    message timestamp >= daemon start) while resetting on daemon
    restart (caller detects mtime change + clears `_token_state`)."""
    pid_file = WS / ".asterism" / "daemon.pid"
    if not pid_file.exists():
        return None
    try:
        return pid_file.stat().st_mtime
    except OSError:
        return None


def _encoded_dir_for_problem(problem: str) -> Path:
    """Mirror claude CLI's project-dir encoding for a problem's cwd.

    Empirically `claude` replaces every non-alphanumeric character in the
    absolute cwd with `-` (so `D:\\Asterism\\Problems\\Geometry\\banach_tarski`
    becomes `D--Asterism-Problems-Geometry-banach-tarski`). All framework
    spawns for a given problem chdir into the same `Problems/<name>/`
    directory, so they share one project dir."""
    rel = problem.replace(".", "/")
    cwd_abs = str((WS / "Problems" / rel).resolve())
    encoded = re.sub(r"[^A-Za-z0-9]", "-", cwd_abs)
    return CLAUDE_PROJECTS_DIR / encoded


def _iso_ge(ts_iso: str, epoch: float) -> bool:
    """ISO8601 timestamp (e.g. '2026-05-27T05:48:00.123Z') ≥ epoch seconds?
    Returns True if unparseable so a malformed line is included rather
    than silently dropped from totals."""
    try:
        s = ts_iso.replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp() >= epoch
    except (ValueError, TypeError, AttributeError):
        return True


def _aggregate_tokens(problem: str, since_ts: float) -> dict:
    """Sum usage across all JSONLs in the problem's project dir whose
    mtime is past `since_ts`, filtered per-message by ISO timestamp.

    Returns {"buckets": {(kind, model): {in,out,cr,cw,spawns}}, "totals": ...}.
    """
    base = _encoded_dir_for_problem(problem)
    buckets: dict[tuple[str, str], dict] = {}

    if not base.exists():
        return {"buckets": buckets,
                "totals": {"in": 0, "out": 0, "cr": 0, "cw": 0, "spawns": 0}}

    for jsonl in base.glob("*.jsonl"):
        try:
            mtime = jsonl.stat().st_mtime
        except OSError:
            continue
        if mtime < since_ts:
            # File hasn't been touched since daemon start — its content
            # belongs to a prior run. Don't bother reading.
            continue

        state = _token_state.setdefault(jsonl, {
            "offset": 0,
            "kind": None,
            "model": None,
            "saw_usage": False,
            # Per-file cumulative usage. The per-tick `buckets` dict is
            # local + fresh each call; with offset caching we'd only
            # see incremental bytes per tick. Store accumulated counts
            # here so totals are CUMULATIVE since watcher start.
            "in": 0, "out": 0, "cr": 0, "cw": 0,
        })

        try:
            with jsonl.open("rb") as f:
                f.seek(state["offset"])
                for line in f:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Classify kind on the first user message that
                    # matches the framework's prompt header. Reflection
                    # and other --resume tails won't re-classify.
                    if state["kind"] is None and d.get("type") == "user" \
                            and not d.get("isMeta"):
                        msg = d.get("message", {})
                        content = msg.get("content", "")
                        if isinstance(content, list) and content:
                            first = content[0]
                            if isinstance(first, dict):
                                content = first.get("text", "")
                            else:
                                content = ""
                        if isinstance(content, str):
                            m = _KIND_RE.match(content)
                            if m:
                                state["kind"] = m.group(1).lower()
                            elif _RESCUE_RE.match(content):
                                state["kind"] = "rescue"
                    # Accumulate usage on assistant messages.
                    if d.get("type") == "assistant":
                        msg = d.get("message", {})
                        if state["model"] is None:
                            state["model"] = msg.get("model") or "unknown"
                        usage = msg.get("usage")
                        ts_iso = d.get("timestamp")
                        if usage and _iso_ge(ts_iso or "", since_ts):
                            state["in"] += int(usage.get(
                                "input_tokens", 0) or 0)
                            state["out"] += int(usage.get(
                                "output_tokens", 0) or 0)
                            state["cr"] += int(usage.get(
                                "cache_read_input_tokens", 0) or 0)
                            state["cw"] += int(usage.get(
                                "cache_creation_input_tokens", 0) or 0)
                            state["saw_usage"] = True
                state["offset"] = f.tell()
        except OSError:
            continue

    # Aggregate per-file cumulative state into (kind, model) buckets.
    for st in _token_state.values():
        if not st["saw_usage"]:
            continue
        key = (st["kind"] or "unknown", st["model"] or "unknown")
        b = buckets.setdefault(key, {
            "in": 0, "out": 0, "cr": 0, "cw": 0, "spawns": 0,
        })
        b["in"] += st["in"]
        b["out"] += st["out"]
        b["cr"] += st["cr"]
        b["cw"] += st["cw"]
        b["spawns"] += 1  # one spawn per JSONL with any usage

    totals = {"in": 0, "out": 0, "cr": 0, "cw": 0, "spawns": 0}
    for b in buckets.values():
        for k in totals:
            totals[k] += b[k]
    return {"buckets": buckets, "totals": totals}


def _fmt_tokens(n: int) -> str:
    """Compact token count: 1234 → '1.2k', 1234567 → '1.2M'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


# Per-model price weights, normalized so Claude Opus 4.7 OUTPUT = 1.0
# unit. Sourced from Anthropic public pricing:
# https://platform.claude.com/docs/en/about-claude/pricing
# Weighted totals expose "share of effective cost / quota burn" rather
# than raw token volume — useful when comparing Opus (Backward) vs
# Sonnet (Builder, Rescue) spend on a monthly-subscription account
# where quota is metered approximately to backend cost.
_PRICE_WEIGHTS: dict[str, dict[str, float]] = {
    # Opus 4.5 / 4.6 / 4.7 share the new (cheaper) pricing tier:
    # $5 input / $25 output / $6.25 cw_5m / $0.50 cr per MTok.
    "claude-opus-4-7": {"in": 0.20, "cw": 0.25, "cr": 0.02, "out": 1.00},
    "claude-opus-4-6": {"in": 0.20, "cw": 0.25, "cr": 0.02, "out": 1.00},
    "claude-opus-4-5": {"in": 0.20, "cw": 0.25, "cr": 0.02, "out": 1.00},
    # Opus 4.1 / 4 legacy tier: 3x the new-Opus rates.
    "claude-opus-4-1": {"in": 0.60, "cw": 0.75, "cr": 0.06, "out": 3.00},
    "claude-opus-4":   {"in": 0.60, "cw": 0.75, "cr": 0.06, "out": 3.00},
    # Sonnet 4.x: $3 / $15 / $3.75 / $0.30 — 0.6x Opus output.
    "claude-sonnet-4-6": {"in": 0.12, "cw": 0.15, "cr": 0.012, "out": 0.60},
    "claude-sonnet-4-5": {"in": 0.12, "cw": 0.15, "cr": 0.012, "out": 0.60},
    "claude-sonnet-4":   {"in": 0.12, "cw": 0.15, "cr": 0.012, "out": 0.60},
    # Haiku 4.5: $1 / $5 / $1.25 / $0.10 — 0.2x Opus output.
    "claude-haiku-4-5": {"in": 0.04, "cw": 0.05, "cr": 0.004, "out": 0.20},
}
# Default for unknown models — assume Sonnet-tier so we don't
# under-count on a new release whose name we haven't catalogued yet.
_DEFAULT_WEIGHTS = _PRICE_WEIGHTS["claude-sonnet-4-6"]


def _weighted_units(bucket: dict, model: str) -> float:
    """Convert a (kind, model) bucket's raw token counts into
    Opus-4.7-output-equivalent units using the per-model price weights
    table. Used to render cost share regardless of which model handled
    each kind."""
    w = _PRICE_WEIGHTS.get(model, _DEFAULT_WEIGHTS)
    return (
        bucket["in"] * w["in"]
        + bucket["cw"] * w["cw"]
        + bucket["cr"] * w["cr"]
        + bucket["out"] * w["out"]
    )


def _render_token_section(usage: dict) -> str:
    """Markdown table of token usage by (kind, model). Returns empty
    string when no data — keeps stats.md tidy on first ticks.

    Adds a `weighted` column (Opus-4.7-output-equivalent units, using
    Anthropic's published per-model token prices) and a `share` column
    showing each row's percentage of total weighted cost. This lets the
    operator compare Opus (Backward) vs Sonnet (Builder, Rescue) spend
    on the same axis, since Opus 4.7 is ~1.67× Sonnet per token, not
    the 5× of older Opus 4.1 tier.
    """
    buckets = usage["buckets"]
    if not buckets:
        return "## token usage (since daemon start)\n\n(no data yet)\n"

    # Compute weighted units per bucket + grand total.
    weighted_map: dict[tuple[str, str], float] = {
        k: _weighted_units(b, k[1]) for k, b in buckets.items()
    }
    weighted_total = sum(weighted_map.values()) or 1.0  # avoid div-by-0

    rows = [
        "| kind | model | in | out | cache_r | cache_w | spawns "
        "| weighted | share |",
        "|---|---|--:|--:|--:|--:|--:|--:|--:|",
    ]
    # Sort by weighted (cost share) descending — most expensive line on top.
    for (kind, model), b in sorted(
        buckets.items(), key=lambda kv: -weighted_map[kv[0]],
    ):
        w = weighted_map[(kind, model)]
        rows.append(
            f"| {kind} | {model} | {_fmt_tokens(b['in'])} "
            f"| {_fmt_tokens(b['out'])} | {_fmt_tokens(b['cr'])} "
            f"| {_fmt_tokens(b['cw'])} | {b['spawns']} "
            f"| {_fmt_tokens(int(w))} | {w / weighted_total * 100:.1f}% |"
        )
    t = usage["totals"]
    rows.append(
        f"| **total** | | **{_fmt_tokens(t['in'])}** "
        f"| **{_fmt_tokens(t['out'])}** | **{_fmt_tokens(t['cr'])}** "
        f"| **{_fmt_tokens(t['cw'])}** | **{t['spawns']}** "
        f"| **{_fmt_tokens(int(weighted_total))}** | |"
    )
    # Cache "hit" share over the full input bill — fresh input + cache
    # writes (paid 1.25×) + cache reads (paid 0.1×). Higher = more of
    # the prompt was served from the cheap cache slot vs re-billed.
    total_input = t["in"] + t["cw"] + t["cr"]
    footnote_lines = [""]
    if total_input > 0:
        footnote_lines.append(
            f"cache hit share: **{t['cr'] / total_input * 100:.1f}%**  "
            f"(`cache_r / (in + cache_w + cache_r)`)"
        )
        footnote_lines.append("")
    footnote_lines.append(
        "weighted basis: Opus 4.7 output = 1 unit  "
        "(Sonnet 4.x out = 0.6, in = 0.12; Opus 4.1 out = 3.0)"
    )
    return ("## token usage (since daemon start)\n\n"
            + "\n".join(rows) + "\n"
            + "\n".join(footnote_lines) + "\n")


def _produced_output(pdir: Path) -> bool:
    """Whether a spawn has written a deliverable (not just input scaffolding).
    The finished-signal for cleanup sub-agents, which open no gateway session
    (so `_session_open` returns None and can't tell finished from running): each
    writes its one output — `simplified.txt` / `refactored.lean` / `annotated.lean`
    / `*.json` — as its last act, so any top-level file that isn't `Context.md`
    or a `_`-prefixed scaffold (`_mcp.jsonl`, `_parser_state.json`, `_progress.md`)
    means the agent finished. Read-only; tolerates a vanishing dir."""
    try:
        for f in pdir.iterdir():
            if (f.is_file() and f.name != "Context.md"
                    and not f.name.startswith("_")):
                return True
    except OSError:
        pass
    return False


_PROC_GRACE = 45.0  # seconds: cold-start (dir created before the worker proc
                    # registers) + finalize (proc exits while the pipeline
                    # commits) grace, so a just-(dis)appeared spawn isn't
                    # mis-judged in the gap process-liveness can't yet see.


def _live_spawn_uuids() -> "set[str] | None":
    """UUIDs of `.attempts/<uuid>/` dirs a live worker process is driving,
    read from process command lines (psutil). Ground-truth pool occupancy:
    the daemon spawns one claude subprocess per in-flight pipeline with the
    spawn dir on its argv, and that subprocess dies when the pipeline
    finishes — so this is immune to a thinking agent that has RELEASED its
    gateway session between gateway calls, which `_session_open` misreads as
    'finished' (the under-count that rendered a busy pool as `0/N`). Returns
    `None` if psutil is unavailable (caller falls back to the older
    session/mtime heuristic). Read-only; tolerates process-teardown races."""
    try:
        import psutil
    except ImportError:
        return None
    uuids: set[str] = set()
    for p in psutil.process_iter(["cmdline"]):
        try:
            cl = " ".join(p.info.get("cmdline") or ())
        except Exception:
            continue
        if ".attempts" not in cl:
            continue
        m = _RE_ATTEMPTS_UUID.search(cl)
        if m:
            uuids.add(m.group(1))
    return uuids


def _active_spawns(limit: int) -> list[Path]:
    """Return up to `limit` most-recently-active spawn dirs (most recent
    first). `limit` is the dispatch pool size.

    A spawn is "active" iff its dir was touched within ACTIVE_WINDOW AND it
    is still in flight. In-flight is decided by PROCESS LIVENESS — a live
    worker process carries the spawn's `.attempts/<uuid>` on its argv — when
    psutil is available; that is the ground-truth signal, immune to a
    thinking agent that released its gateway session between gateway calls
    (the bug that showed a busy pool as `0/N`). Only when psutil is
    unavailable do we fall back to the older `_session_open` /
    `_produced_output` heuristic (which under-counts think-heavy spawns).
    `_PROC_GRACE` keeps a just-spawned dir whose worker hasn't registered yet
    and a just-finished dir still being committed.
    """
    if not ATTEMPTS_DIR.exists():
        return []
    now = time.time()
    cutoff = now - ACTIVE_WINDOW
    live = _live_spawn_uuids()
    scored: list[tuple[float, Path]] = []
    for pdir in ATTEMPTS_DIR.iterdir():
        if not pdir.is_dir():
            continue
        # Skip the dedupe-check loose files that live directly under
        # .attempts/ (not in a per-spawn dir of their own).
        if pdir.name.startswith("_"):
            continue
        s = _spawn_score(pdir)
        if s < cutoff:
            continue
        if live is not None:
            # Ground truth: a live worker process drives this dir → in flight,
            # even mid-thought with the gateway session released. No live
            # process AND not freshly touched → finished (the production daemon
            # rmtree's the dir; an e2e lingering dir ages past _PROC_GRACE).
            if pdir.name not in live and s < now - _PROC_GRACE:
                continue
        else:
            sess = _session_open(pdir)
            if sess is False:
                continue  # session released → finished; skip lingering dir
            if sess is None and _produced_output(pdir):
                continue  # cleanup sub-agent that already wrote its deliverable
        scored.append((s, pdir))
    scored.sort(reverse=True)
    return [p for _, p in scored[:limit]]


def _latest_lean_in(spawn_dir: Path) -> Path | None:
    """The most-recently-modified .lean in this spawn dir tree, or None.

    TOCTOU-safe against framework cleanup: the framework rmtree's spawn
    dirs at spawn finish, and both the rglob walk and the per-file
    stat() can race that deletion. The earlier `max(..., key=p.stat())`
    let any FileNotFoundError from a vanished file kill the whole
    watcher process (observed 2026-05-22 on the Topology.brouwer run:
    `new_closedball_stdsimplex_homeo_data_zero.lean` was rmtree'd
    between rglob and stat → watcher exited 1 → demo panes stopped
    refreshing). Drop any file whose stat() fails instead.
    """
    try:
        files = list(spawn_dir.rglob("*.lean"))
    except OSError:
        return None
    if not files:
        return None
    latest: Path | None = None
    latest_mtime = float("-inf")
    for f in files:
        try:
            mt = f.stat().st_mtime
        except OSError:
            continue
        if mt > latest_mtime:
            latest_mtime = mt
            latest = f
    return latest


# Cap worker labels to keep stats.md visually narrow. Long miniF2F
# slugs (`algebra_amgm_sqrtxymulxmyeqxpy_xpygeq4`) wrap badly in the
# centre pane otherwise.
_LABEL_SLUG_MAX = 36


def _lookup_spawn_info(spawn_dir: Path) -> tuple[str, str] | None:
    """Identify the spawn's pipeline kind + label by parsing its
    `Context.md`. Returns (kind, slug_or_problem) or None if Context.md
    is missing / unreadable.

    Why Context.md and not the `pipelines` table: pipelines rows are
    INSERT'd at spawn FINISH (db.record_pipeline), but `.attempts/<uuid>/`
    is rmtree'd shortly thereafter — so a DB lookup almost never resolves
    while the spawn dir is still on disk. Context.md is written at the
    start of cold spawn (`compile_context` / `compile_strategist_context`
    / `compile_forward_context`) and carries unambiguous signatures.
    """
    ctx = spawn_dir / "Context.md"
    if not ctx.exists():
        # The incremental migrate spawns each hole in a `decl-<slug>/`
        # subdir, each with its own Context.md; the top-level spawn dir has
        # none. Fall back to any one subdir's Context.md so the pipeline is
        # still labelled (e.g. "migrate") instead of "spawning, ?". The
        # watcher adapts to the on-disk layout — the pipeline code is never
        # changed for the observer's benefit (non-invasive).
        for sub in sorted(spawn_dir.glob("*/Context.md")):
            info = _lookup_spawn_info(sub.parent)
            if info is not None:
                return info
        return None
    try:
        # Read the whole file. Earlier versions capped at 80 / 300 lines,
        # but BRIEF.md inlined at the top grew with richer Manifests and
        # kept overflowing the cap (residue_thm 2026-05-19: BRIEF 81
        # lines pushed the `# Context for goal <slug>` header to line
        # 82, stats showed every spawn as `spawning, ?`). Any constant
        # is brittle. Context.md is tens of KB at most; reading the
        # whole file each watcher tick is microseconds.
        with open(ctx, "r", encoding="utf-8", errors="replace") as f:
            head_lines = [line.rstrip("\n") for line in f]
    except OSError:
        return None
    # Strategist / Forward declare themselves in the file's first header.
    for line in head_lines[:6]:
        m = _RE_STRATEGIST_CTX.match(line)
        if m:
            return ("strategist", m.group(1))
        m = _RE_FORWARD_CTX.match(line)
        if m:
            return ("forward", m.group(1))
        m = _RE_LIBRARIAN_CTX.match(line)
        if m:
            # kind = the work-kind (dedup/classify/migrate/cleanup/bridge);
            # label = the problem (truncated like the goal-slug labels).
            kind, prob = m.group(1), m.group(2)
            # migrate carries `## Migrate file `<path>`` — append the file
            # basename so stats reads "migrate <File>.lean" (which file is in
            # flight), not just "migrate". Read-only; the line already exists.
            for ln in head_lines:
                fm = _RE_LIBRARIAN_MIGRATE_FILE.match(ln)
                if fm:
                    kind = f"{kind} {fm.group(1).rsplit('/', 1)[-1]}"
                    break
            if len(prob) > _LABEL_SLUG_MAX:
                prob = prob[: _LABEL_SLUG_MAX - 1] + "…"
            return (kind, prob)
        # Cleanup sub-agents: `# <Title> — <problem>[ — `<file>`]`. Label by the
        # stage (`cleanup:variables` etc.) + the file/decl it's working on.
        m = _RE_CLEANUP_CTX.match(line)
        if m and m.group(1) in _CLEANUP_TITLES:
            kind, label = _CLEANUP_TITLES[m.group(1)], m.group(3)
            if label is None:           # dedup audit: file is on `# file: <rel>`
                for ln in head_lines[:4]:
                    fm = _RE_CLEANUP_FILE.match(ln)
                    if fm:
                        label = fm.group(1)
                        break
            label = (label or m.group(2)).rsplit("/", 1)[-1]
            if len(label) > _LABEL_SLUG_MAX:
                label = label[: _LABEL_SLUG_MAX - 1] + "…"
            return (kind, label)
    # Backward + Builder share `# Context for goal <slug>` header.
    # Backward additionally renders a `## Strategy naming` section
    # (context.py:_section_strategy_naming, omitted when strategy_id
    # is None — i.e. Builder).
    slug: str | None = None
    has_strategy_naming = False
    for line in head_lines:
        if slug is None:
            m = _RE_CONTEXT_GOAL.match(line)
            if m:
                slug = m.group(1)
        if _RE_STRATEGY_NAMING.match(line):
            has_strategy_naming = True
            break
    if slug is None:
        return None
    kind = "backward" if has_strategy_naming else "builder"
    if len(slug) > _LABEL_SLUG_MAX:
        slug = slug[: _LABEL_SLUG_MAX - 1] + "…"
    return (kind, slug)


# Fixed VS Code layout: 4 file panes for worker spawn content. Pool
# size can exceed this; stats will list all live pipelines. Pane content
# for inactive slots is left on its last-seen value — clearing every
# tick would flash the panes (cf. original ACTIVE_WINDOW comment).
WORKER_PANE_COUNT = 4


_PANE_IDLE_PLACEHOLDER = "-- (idle, waiting for spawn)\n"

# Gateway pool slot id ∈ {0..pool-1}. Each spawn's _mcp.jsonl first
# line is the `session_registered` event with `claimed_slot` = the
# slot it acquired from the gateway pool (1:1 binding for the spawn's
# lifetime per `lsp/gateway.py:WorkerSlot`). We map worker pane N to
# gateway slot N-1 directly — stable for the entire spawn lifecycle,
# no shifting, no UUID bookkeeping.
import json as _json


def _spawn_claimed_slot(pdir: Path) -> int | None:
    """Read `claimed_slot` from the first `session_registered` event in
    the spawn dir's `_mcp.jsonl`. Returns None if file missing /
    unreadable / no register event yet (cold-start before slot
    acquired). Cheap — reads at most a few lines."""
    mcp = pdir / "_mcp.jsonl"
    if not mcp.exists():
        return None
    try:
        with open(mcp, "r", encoding="utf-8") as f:
            for _ in range(5):  # register event is line 1; cap defensively
                line = f.readline()
                if not line:
                    return None
                try:
                    obj = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                if obj.get("event") == "session_registered":
                    slot = obj.get("claimed_slot")
                    if isinstance(slot, int):
                        return slot
                    return None
    except OSError:
        return None
    return None


def _update_worker_panes(
    spawns: list[Path],
) -> list[tuple[str, str] | None]:
    """Map active spawns into worker panes by their gateway pool slot
    id. Worker pane N+1 ↔ gateway slot N. The gateway holds 4
    `lean-asterism-server` workers for the entire daemon run; spawns
    claim and release their slot, but slot identity is permanent.
    A pane therefore represents a long-lived gateway worker, not a
    transient spawn.

    Behaviour:
      - Spawn currently in slot K → worker_(K+1).lean = its latest .lean
      - No spawn in slot K → pane retains last spawn's content (the
        "what this worker last did" view). No reset to idle, no flash.
        Initial placeholder is written once at watcher startup by main().

    Returns one label per spawn in input order (newest-first) for the
    stats pipeline list. Strategist + spawns that haven't yet emitted
    `session_registered` (cold pre-claim) appear in stats labels but
    consume no pane.
    """
    active_labels: list[tuple[str, str] | None] = [None] * len(spawns)
    slot_to_spawn: dict[int, Path] = {}
    for i, spawn in enumerate(spawns):
        info = _lookup_spawn_info(spawn)
        active_labels[i] = info if info is not None else ("spawning", "?")
        slot = _spawn_claimed_slot(spawn)
        if slot is not None and 0 <= slot < WORKER_PANE_COUNT:
            slot_to_spawn[slot] = spawn

    for slot, spawn in slot_to_spawn.items():
        latest = _latest_lean_in(spawn)
        if latest is None:
            continue
        target = ACTIVE_DIR / f"worker_{slot + 1}.lean"
        try:
            shutil.copy2(latest, target)
        except OSError:
            pass
    return active_labels


def _update_tree(problem: str) -> bool:
    # Dotted slug -> nested path (same convention as db.problem_dir):
    # "Topology.brouwer_fixed_point" -> Problems/Topology/brouwer_fixed_point/.
    # Earlier code used `Problems / problem` literally, which silently
    # missed any dotted slug (Minif2f.*, Topology.*, etc) — the TREE pane
    # then stayed on the startup placeholder for the entire run.
    src = WS / "Problems" / Path(*problem.split(".")) / "TREE.md"
    if not src.exists():
        return False
    shutil.copy2(src, ACTIVE_DIR / "tree.md")
    return True


# Librarian library_decls lifecycle, in pipeline order. Terminal dropped/cited
# are excluded — they never get a Library file. Used by the Librarian section.
_LIB_STAGES = ("candidate", "deduped", "classified", "migrated", "cleaned")


def _librarian_index_has(problem: str) -> bool:
    """Read-only: True iff Library/INDEX.md records `problem` (Librarian
    finished). Inlined from dispatcher._librarian_index_has to keep the
    watcher import-light and strictly observational."""
    index = WS / "Library" / "INDEX.md"
    if not index.exists():
        return False
    header = f"## {problem}"
    return any(ln.strip() == header for ln in
               index.read_text(encoding="utf-8", errors="replace").splitlines())


def _librarian_section(conn, problem: str) -> str:
    """Markdown for the Librarian pipeline (dedup→classify→migrate→cleanup→
    bridge), or '' when it isn't running — no `library_decls` rows yet (still
    in the proof phase) or INDEX already written (finished). Pure SELECT +
    file read; non-invasive like the rest of the watcher."""
    from collections import Counter, defaultdict
    try:
        rows = conn.execute(
            "SELECT lifecycle, target_file FROM library_decls WHERE problem=?",
            (problem,),
        ).fetchall()
    except sqlite3.Error:
        return ""
    if not rows:
        return ""  # not started (still proving) → hide
    counts = Counter(r["lifecycle"] for r in rows)
    # Show while any in-pipeline work remains; hide only when truly finished —
    # INDEX written AND nothing left mid-pipeline. "INDEX present" alone isn't
    # "done": re-cleaning an already-promoted problem (dev-scratch re-test via
    # `run --scope`) keeps its stale INDEX entry while decls sit at `migrated`.
    active = any(counts.get(s) for s in
                 ("candidate", "deduped", "classified", "migrated"))
    if _librarian_index_has(problem) and not active:
        return ""
    keep = sum(counts.get(s, 0) for s in _LIB_STAGES)
    # Phase = the least-advanced in-pipeline stage still present.
    if counts.get("candidate"):
        phase = "dedup"
    elif counts.get("deduped"):
        phase = "classify"
    elif counts.get("classified"):
        phase = "migrate"
    elif counts.get("migrated"):
        phase = "cleanup"
    else:
        phase = "bridge"  # all cleaned, INDEX pending
    migrated = counts.get("migrated", 0) + counts.get("cleaned", 0)
    cleaned = counts.get("cleaned", 0)

    # Per-file state = the least-advanced stage among its decls (a file only
    # advances once ALL its decls migrate / clean together).
    byf: dict = defaultdict(list)
    for r in rows:
        if r["target_file"] and r["lifecycle"] in _LIB_STAGES:
            byf[r["target_file"]].append(r["lifecycle"])
    lines = [
        "## library (Librarian)", "",
        f"**phase**: {phase}  ·  keep {keep} / dropped "
        f"{counts.get('dropped', 0)} / cited {counts.get('cited', 0)}", "",
        f"decls: migrated {migrated}/{keep} · cleaned {cleaned}/{keep}", "",
    ]
    if byf:
        lines += ["| file | decls | state |", "|---|--:|---|"]
        for tf in sorted(byf):
            st = min(byf[tf], key=_LIB_STAGES.index)
            lines.append(f"| {tf.split('/')[-1]} | {len(byf[tf])} | {st} |")
        lines.append("")
    return "\n".join(lines)


def _write_stats(
    problem: str,
    active_labels: list[tuple[str, str] | None],
    started_at: float,
    pool_size: int,
    token_section: str = "",
) -> None:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        goals = conn.execute(
            "SELECT status, count(*) c FROM goals WHERE problem=? "
            "GROUP BY status",
            (problem,),
        ).fetchall()
        gcounts = {r["status"]: r["c"] for r in goals}
        strategies = conn.execute(
            "SELECT count(*) FROM strategies s JOIN goals g "
            "ON s.goal_id = g.id WHERE g.problem = ?",
            (problem,),
        ).fetchone()[0]
        succeeded = conn.execute(
            "SELECT count(*) FROM strategies s JOIN goals g "
            "ON s.goal_id = g.id "
            "WHERE g.problem = ? AND s.status = 'succeeded'",
            (problem,),
        ).fetchone()[0]
        lib_section = _librarian_section(conn, problem)
        conn.close()
    except sqlite3.Error as e:
        (ACTIVE_DIR / "stats.md").write_text(
            f"# stats — error\n\n```\n{e}\n```\n", encoding="utf-8",
        )
        return

    elapsed = int(time.time() - started_at)
    h, rem = divmod(elapsed, 3600)
    m, s = divmod(rem, 60)
    wall = f"{h:02d}:{m:02d}:{s:02d}"

    proved = gcounts.get("proved", 0)
    attempting = gcounts.get("attempting", 0)
    open_g = gcounts.get("open", 0)
    shelved = gcounts.get("shelved", 0)
    total = sum(gcounts.values())

    # Pool-centric: the dispatch.pool size is the denominator and the
    # listed rows are only the in-flight pipelines (no idle row noise).
    # active_labels carries up to pool_size entries; non-None ones are
    # the live pipelines. Pane mapping (worker_1.lean .. worker_4.lean)
    # is independent of this listing — file panes stay capped at 4.
    live = [lbl for lbl in active_labels if lbl is not None]
    if live:
        pipelines_block = "".join(
            f"- {kind}, `{slug}`\n" for kind, slug in live
        )
    else:
        pipelines_block = "(no pipelines in flight)\n"

    body = (
        f"# {problem}\n\n"
        f"**wall clock**: `{wall}`\n\n"
        f"**goals**: proved {proved} / attempting {attempting} / "
        f"open {open_g} / shelved {shelved}  (total {total})\n\n"
        f"**strategies**: {succeeded} succeeded / {strategies} total\n\n"
        + (lib_section + "\n" if lib_section else "")
        + f"## active pipelines ({len(live)}/{pool_size})\n\n"
        f"{pipelines_block}"
    )
    if token_section:
        body += "\n" + token_section
    (ACTIVE_DIR / "stats.md").write_text(body, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--problem", required=True,
        help="problem slug, e.g. sl2_v_n_irreducible",
    )
    ap.add_argument(
        "--interval", type=float, default=1.0,
        help="poll period in seconds (default 1.0)",
    )
    ap.add_argument(
        "--keep-stale", action="store_true",
        help=("don't clear worker_*.lean / tree.md on startup. Default "
              "is to clear (better for demo recording — a fresh take "
              "starts with clean placeholder content). Set this flag "
              "to preserve last-take content between takes."),
    )
    args = ap.parse_args()

    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    # Init placeholders. Default behavior (no --keep-stale): always
    # overwrite, so a fresh watcher run starts with clean panes (new
    # takes shouldn't inherit stale content from prior spawns).
    placeholder_worker = "-- (idle, waiting for spawn)\n"
    placeholder_tree = "_(waiting for framework to write TREE.md)_\n"
    for i in range(1, 5):
        f = ACTIVE_DIR / f"worker_{i}.lean"
        if args.keep_stale and f.exists():
            continue
        f.write_text(placeholder_worker, encoding="utf-8")
    tree = ACTIVE_DIR / "tree.md"
    if not (args.keep_stale and tree.exists()):
        tree.write_text(placeholder_tree, encoding="utf-8")

    started_at = time.time()
    pool_size = _pool_size()
    print(f"[demo-watcher] problem={args.problem}, "
          f"interval={args.interval}s, active dir={ACTIVE_DIR}, "
          f"keep_stale={args.keep_stale}, pool_size={pool_size}",
          flush=True)

    # Token aggregation runs every TOKEN_REFRESH_SEC instead of every
    # tick — scanning all of the problem's JSONLs (often dozens of files,
    # some hundreds of KB each) on a 1s tick is wasteful when the data
    # only changes when a spawn writes a new assistant message. Result is
    # cached between refreshes so stats.md still updates every tick.
    TOKEN_REFRESH_SEC = 60.0
    last_token_refresh = 0.0
    token_section_cache = ""
    # Daemon-restart detection: if `daemon.pid` mtime advances mid-watcher
    # we're tracking a different daemon now → reset per-file accumulator
    # so we don't mix old daemon's tokens into the new run's totals.
    last_daemon_start: float | None = None

    try:
        while True:
            spawns = _active_spawns(limit=pool_size)
            active_labels = _update_worker_panes(spawns)
            _update_tree(args.problem)
            now = time.time()
            if now - last_token_refresh >= TOKEN_REFRESH_SEC:
                try:
                    # Anchor token accounting to current daemon's start
                    # (pid file mtime). Fall back to watcher start if no
                    # daemon is running — display shows "(no data)" but
                    # the call doesn't crash.
                    daemon_start = _daemon_start_time()
                    since = daemon_start if daemon_start is not None \
                        else started_at
                    if last_daemon_start is not None \
                            and daemon_start is not None \
                            and daemon_start > last_daemon_start + 1.0:
                        # Daemon restarted while watcher kept running.
                        # Per-file cumulative state belongs to the old
                        # daemon's run — drop and re-aggregate fresh.
                        _token_state.clear()
                    last_daemon_start = daemon_start
                    usage = _aggregate_tokens(args.problem, since_ts=since)
                    token_section_cache = _render_token_section(usage)
                except Exception as exc:  # noqa: BLE001
                    token_section_cache = (
                        f"## token usage (since daemon start)\n\n"
                        f"_(aggregation error: {exc})_\n")
                last_token_refresh = now
            _write_stats(args.problem, active_labels, started_at,
                         pool_size, token_section=token_section_cache)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[demo-watcher] stopped", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
