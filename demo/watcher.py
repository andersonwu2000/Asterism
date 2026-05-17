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
import shutil
import sqlite3
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
ACTIVE_DIR = WS / "demo" / "active"
ATTEMPTS_DIR = WS / ".attempts"
DB_PATH = WS / "asterism.db"

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


def _lookup_spawn_info(pipeline_id: str) -> tuple[str, str] | None:
    """Return `(kind_lower, goal_slug_or_problem)` for a spawn whose
    `.attempts/<uuid>/` matches `pipeline_id`. Returns None if no
    pipelines row exists yet (the worker just started and the
    dispatcher hasn't recorded the row), or on DB error.

    Forward (target_kind='Problem') falls back to the problem name as
    the label since the spawn isn't tied to a single goal.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT kind, target_id, target_kind FROM pipelines "
            "WHERE id = ?", (pipeline_id,),
        ).fetchone()
        if row is None:
            conn.close()
            return None
        kind = str(row["kind"]).lower()
        if row["target_kind"] == "Problem":
            label = str(row["target_id"])
        else:
            g = conn.execute(
                "SELECT slug FROM goals WHERE id = ?",
                (int(row["target_id"]),),
            ).fetchone()
            label = g["slug"] if g else str(row["target_id"])
        conn.close()
    except (sqlite3.Error, ValueError):
        return None
    if len(label) > _LABEL_SLUG_MAX:
        label = label[: _LABEL_SLUG_MAX - 1] + "…"
    return (kind, label)


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
        info = _lookup_spawn_info(spawn.name)
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
