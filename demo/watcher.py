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
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
ACTIVE_DIR = WS / "demo" / "active"
ATTEMPTS_DIR = WS / ".attempts"
DB_PATH = WS / "asterism.db"

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

# Spawns whose dir contained a .lean touched in the last ACTIVE_WINDOW
# seconds are treated as "live". Past that, the spawn has likely
# committed back and wound down; we leave its pane on the last-seen
# content rather than clearing, so the pane doesn't flash.
ACTIVE_WINDOW = 60.0


def _spawn_score(pdir: Path) -> float:
    """Most recent mtime of any .lean directly under `<pdir>/` (and any
    sub-tree), or -inf if no .lean exists. Used to pick the most
    recently active spawn dir.

    Framework writes `patch.lean` / `new_*.lean` directly inside
    `.attempts/<uuid>/` (flat layout); earlier framework versions used
    `<uuid>/sandbox/` — `rglob` covers both transparently.
    """
    latest = float("-inf")
    try:
        for f in pdir.rglob("*.lean"):
            try:
                t = f.stat().st_mtime
            except OSError:
                continue
            if t > latest:
                latest = t
    except OSError:
        return float("-inf")
    return latest


def _active_spawns() -> list[Path]:
    """Return up to 4 most-recently-active spawn dirs (most recent first).

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
    return [p for _, p in scored[:4]]


def _latest_lean_in(spawn_dir: Path) -> Path | None:
    """The most-recently-modified .lean in this spawn dir tree, or None."""
    try:
        files = list(spawn_dir.rglob("*.lean"))
    except OSError:
        return None
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


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
        # Signature lines all sit in the first ~50 lines; cap the read.
        with open(ctx, "r", encoding="utf-8", errors="replace") as f:
            head_lines = []
            for i, line in enumerate(f):
                if i >= 80:
                    break
                head_lines.append(line.rstrip("\n"))
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


def _update_worker_panes(
    spawns: list[Path],
) -> list[tuple[str, str] | None]:
    """Copy each active spawn's latest .lean into the matching worker
    pane and return per-pane (kind, slug) labels. The labels come from
    the pipelines table — much more readable than the on-disk file
    path (`patch.lean` everywhere) for the stats pane."""
    active_labels: list[tuple[str, str] | None] = [None] * 4
    for i, spawn in enumerate(spawns):
        latest = _latest_lean_in(spawn)
        if latest is None:
            continue
        target = ACTIVE_DIR / f"worker_{i + 1}.lean"
        try:
            shutil.copy2(latest, target)
        except OSError:
            continue
        info = _lookup_spawn_info(spawn)
        active_labels[i] = info if info is not None else ("spawning", "?")
    return active_labels


def _update_tree(problem: str) -> bool:
    src = WS / "Problems" / problem / "TREE.md"
    if not src.exists():
        return False
    shutil.copy2(src, ACTIVE_DIR / "tree.md")
    return True


def _write_stats(
    problem: str,
    active_labels: list[tuple[str, str] | None],
    started_at: float,
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

    workers_block = ""
    for i, label in enumerate(active_labels):
        if label is None:
            workers_block += f"- worker {i + 1}: idle\n"
        else:
            kind, slug = label
            workers_block += f"- worker {i + 1}: {kind}, `{slug}`\n"

    body = (
        f"# {problem}\n\n"
        f"**wall clock**: `{wall}`\n\n"
        f"**goals**: proved {proved} / attempting {attempting} / "
        f"open {open_g} / shelved {shelved}  (total {total})\n\n"
        f"**strategies**: {succeeded} succeeded / {strategies} total\n\n"
        f"## active workers\n\n{workers_block}"
    )
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
    print(f"[demo-watcher] problem={args.problem}, "
          f"interval={args.interval}s, active dir={ACTIVE_DIR}, "
          f"keep_stale={args.keep_stale}",
          flush=True)

    try:
        while True:
            spawns = _active_spawns()
            active_labels = _update_worker_panes(spawns)
            _update_tree(args.problem)
            _write_stats(args.problem, active_labels, started_at)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[demo-watcher] stopped", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
