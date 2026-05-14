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

# Spawns whose sandbox/ was touched in the last ACTIVE_WINDOW seconds are
# treated as "live". Past that, the spawn has likely committed back and
# wound down; we leave its pane on the last-seen content rather than
# clearing, so the pane doesn't flash.
ACTIVE_WINDOW = 60.0


def _spawn_score(pdir: Path) -> float:
    """Most recent mtime of any .lean under <pdir>/sandbox/, or -inf."""
    sandbox = pdir / "sandbox"
    if not sandbox.exists():
        return float("-inf")
    latest = float("-inf")
    for f in sandbox.rglob("*.lean"):
        try:
            t = f.stat().st_mtime
        except OSError:
            continue
        if t > latest:
            latest = t
    return latest


def _active_spawns() -> list[Path]:
    """Return up to 4 most-recently-active spawn dirs (most recent first).

    A spawn is "active" iff some .lean under its sandbox/ was touched
    within ACTIVE_WINDOW seconds. Ignores spawns whose sandbox is empty
    or whose all files are older than the window.
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
    sandbox = spawn_dir / "sandbox"
    if not sandbox.exists():
        return None
    files = list(sandbox.rglob("*.lean"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _update_worker_panes() -> list[str | None]:
    spawns = _active_spawns()
    active_paths: list[str | None] = [None] * 4
    for i, spawn in enumerate(spawns):
        latest = _latest_lean_in(spawn)
        if latest is None:
            continue
        target = ACTIVE_DIR / f"worker_{i + 1}.lean"
        try:
            shutil.copy2(latest, target)
        except OSError:
            continue
        try:
            active_paths[i] = str(latest.relative_to(WS))
        except ValueError:
            active_paths[i] = str(latest)
    return active_paths


def _update_tree(problem: str) -> bool:
    src = WS / "Problems" / problem / "TREE.md"
    if not src.exists():
        return False
    shutil.copy2(src, ACTIVE_DIR / "tree.md")
    return True


def _write_stats(
    problem: str, active_paths: list[str | None], started_at: float,
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
    for i, p in enumerate(active_paths):
        if p is None:
            workers_block += f"- worker {i + 1}: idle\n"
        else:
            workers_block += f"- worker {i + 1}: `{p}`\n"

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
    args = ap.parse_args()

    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(1, 5):
        f = ACTIVE_DIR / f"worker_{i}.lean"
        if not f.exists():
            f.write_text("-- (idle, waiting for spawn)\n", encoding="utf-8")
    if not (ACTIVE_DIR / "tree.md").exists():
        (ACTIVE_DIR / "tree.md").write_text(
            "_(waiting for framework to write TREE.md)_\n",
            encoding="utf-8",
        )

    started_at = time.time()
    print(f"[demo-watcher] problem={args.problem}, "
          f"interval={args.interval}s, active dir={ACTIVE_DIR}",
          flush=True)

    try:
        while True:
            active_paths = _update_worker_panes()
            _update_tree(args.problem)
            _write_stats(args.problem, active_paths, started_at)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[demo-watcher] stopped", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
