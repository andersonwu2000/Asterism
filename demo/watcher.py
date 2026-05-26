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
_RE_STRATEGY_NAMING = re.compile(r"^## Strategy naming\b")

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

# Persistent per-file state. Survives across watcher ticks so we only
# parse the new bytes appended since the last read. Cleared if watcher
# restarts (in-memory only).
_token_state: dict[Path, dict] = {}


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


def _render_token_section(usage: dict) -> str:
    """Markdown table of token usage by (kind, model). Returns empty
    string when no data — keeps stats.md tidy on first ticks."""
    buckets = usage["buckets"]
    if not buckets:
        return "## token usage (since daemon start)\n\n(no data yet)\n"

    header = (
        f"{'kind':<12} {'model':<22} {'in':>8} {'out':>7} "
        f"{'cache_r':>9} {'cache_w':>8} {'spawns':>6}"
    )
    sep = "-" * len(header)
    rows = [header, sep]
    for (kind, model), b in sorted(buckets.items(),
                                    key=lambda kv: -kv[1]["in"]):
        rows.append(
            f"{kind:<12} {model:<22} "
            f"{_fmt_tokens(b['in']):>8} {_fmt_tokens(b['out']):>7} "
            f"{_fmt_tokens(b['cr']):>9} {_fmt_tokens(b['cw']):>8} "
            f"{b['spawns']:>6}"
        )
    t = usage["totals"]
    rows.append(sep)
    rows.append(
        f"{'total':<35} "
        f"{_fmt_tokens(t['in']):>8} {_fmt_tokens(t['out']):>7} "
        f"{_fmt_tokens(t['cr']):>9} {_fmt_tokens(t['cw']):>8} "
        f"{t['spawns']:>6}"
    )
    # Cache "hit" share over the full input bill — fresh input + cache
    # writes (paid 1.25×) + cache reads (paid 0.1×). Higher = more of
    # the prompt was served from the cheap cache slot vs re-billed.
    total_input = t["in"] + t["cw"] + t["cr"]
    cache_line = ""
    if total_input > 0:
        cache_line = (f"\ncache hit share: "
                      f"{t['cr'] / total_input * 100:.1f}%  "
                      f"(cache_r / (in + cache_w + cache_r))")
    return ("## token usage (since daemon start)\n\n"
            "```\n" + "\n".join(rows) + cache_line + "\n```\n")


def _active_spawns(limit: int) -> list[Path]:
    """Return up to `limit` most-recently-active spawn dirs
    (most recent first). `limit` is the dispatch pool size — at any
    given moment the daemon can have at most that many spawns in
    flight, so picking more would just surface stale dirs.

    A spawn is "active" iff some .lean inside its dir was touched within
    ACTIVE_WINDOW seconds. Empty / stale dirs are skipped.
    """
    if not ATTEMPTS_DIR.exists():
        return []
    cutoff = time.time() - ACTIVE_WINDOW
    scored: list[tuple[float, Path]] = []
    for pdir in ATTEMPTS_DIR.iterdir():
        if not pdir.is_dir():
            continue
        # Skip the dedupe-check loose files that live directly under
        # .attempts/ (not in a per-spawn dir of their own).
        if pdir.name.startswith("_"):
            continue
        s = _spawn_score(pdir)
        if s >= cutoff:
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
        f"## active pipelines ({len(live)}/{pool_size})\n\n"
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

    try:
        while True:
            spawns = _active_spawns(limit=pool_size)
            active_labels = _update_worker_panes(spawns)
            _update_tree(args.problem)
            now = time.time()
            if now - last_token_refresh >= TOKEN_REFRESH_SEC:
                try:
                    usage = _aggregate_tokens(args.problem,
                                              since_ts=started_at)
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
