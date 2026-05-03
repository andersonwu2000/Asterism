"""Daemon-startup recovery — reconcile transient state from a crashed
prior daemon back to a consistent baseline.

Extracted from `dispatcher.py` (P2-#4 audit). The dispatcher's main
loop concerns itself with steady-state work; FS↔DB reconciliation is
a structurally separate phase that runs once at startup.

Five classes of stale state, each restored:

  1. queue rows         — live dispatch state, never persists across
                          daemon lifetimes; cleared unconditionally.
  2. half-baked strategies — INSERTed by run_backward then crashed
                          before scratch_path was set; flagged 'dead'.
  3. stuck-attempting goals — Backward succeeded last run but no
                          'proposed' strategy survives now (all dead/
                          superseded). Reset to 'open' so bfs_refill
                          can dispatch a fresh Backward.
  4. orphan .attempts/<pid>/ dirs — daemon SIGKILL bypasses
                          WorkArea.__exit__; child claude subprocesses
                          can keep writing to a dead parent's sandbox.
  5. orphan .lean.{backup,verify_backup,verify_backup_s<id>,tmp}
                          files — Builder/Verify died mid-write,
                          leaving the original next to a half-applied
                          patch (or vice versa). Restore from backup
                          unless the corresponding goal is already
                          'proved' (race window between lake-build
                          success and backup.unlink); then just
                          delete. .tmp files are always discarded.

Skip filesystem sweeps if workspace is None (test fixtures call
DB-only). Orphan lean files placed by killed Backward in proofs/ are
NOT touched here — they're handled by the post-success reconcile +
prune path (`prune.reconcile_proved_goals` / `prune.prune_problem`).
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from . import db


def recover_at_startup(conn: sqlite3.Connection,
                       workspace: Path | None = None) -> None:
    queue_cleared = conn.execute("DELETE FROM queue").rowcount

    strategies_killed = conn.execute(
        "UPDATE strategies SET status = 'dead'"
        " WHERE status = 'proposed' AND scratch_path = ''"
    ).rowcount

    goals_reopened = conn.execute(
        "UPDATE goals SET status = 'open', updated_at = ?"
        " WHERE status = 'attempting'"
        "   AND NOT EXISTS ("
        "     SELECT 1 FROM strategies"
        "     WHERE goal_id = goals.id AND status = 'proposed'"
        "   )",
        (db.now(),),
    ).rowcount

    conn.commit()

    attempts_cleared = 0
    backups_handled = 0
    tmps_removed = 0
    if workspace is not None:
        attempts_root = workspace / ".attempts"
        if attempts_root.exists():
            for d in attempts_root.iterdir():
                if d.is_dir():
                    try:
                        shutil.rmtree(d)
                        attempts_cleared += 1
                    except OSError:
                        pass  # claude subprocess may still hold a handle

        backups_handled, tmps_removed = sweep_lean_backups(conn, workspace)

    if (queue_cleared or strategies_killed or goals_reopened
            or attempts_cleared or backups_handled or tmps_removed):
        print(f"[dispatcher] recovery: cleared {queue_cleared} queue rows, "
              f"killed {strategies_killed} half-baked strategies, "
              f"reopened {goals_reopened} stuck goals, "
              f"removed {attempts_cleared} orphan attempts dirs, "
              f"handled {backups_handled} lean backups, "
              f"removed {tmps_removed} stale .tmp files",
              flush=True)


def sweep_lean_backups(conn: sqlite3.Connection,
                       workspace: Path) -> tuple[int, int]:
    """Restore or discard `*.lean.{backup,verify_backup,verify_backup_s*}`
    and remove `*.lean.tmp` files left by killed Builder/Verify pipelines.

    Decision per backup file:
      - If the corresponding goal is 'proved' in DB, the daemon died
        in the microsecond window between lake-build success and
        backup.unlink. The current .lean is the validated proof —
        just discard the backup.
      - Otherwise (goal 'open' / 'attempting' / 'shelved'), the
        pipeline did not commit success. Restore .lean from backup,
        then unlink the backup.

    .tmp files (Verify's atomic-write candidate) are always removed
    unread — partial content, never safe to use.
    """
    backups_handled = 0
    tmps_removed = 0
    problems_root = workspace / "Problems"
    if not problems_root.exists():
        return 0, 0

    goal_status = {
        r["lean_path"]: r["status"]
        for r in conn.execute("SELECT lean_path, status FROM goals")
    }

    # P0-#1 added sid-keyed backups (`.lean.verify_backup_s<id>`) so
    # concurrent Verifies on sibling strategies don't clobber each
    # other. Glob both the legacy plain suffix and the sid-suffixed
    # variant. Missing this would let sid-keyed orphans accumulate
    # forever after a daemon crash mid-Verify.
    backup_globs = ["**/*.lean.backup",
                    "**/*.lean.verify_backup",
                    "**/*.lean.verify_backup_s*"]
    for pattern in backup_globs:
        for backup in problems_root.glob(pattern):
            original = backup.with_suffix("")  # strips just last suffix
            try:
                rel = original.relative_to(workspace).as_posix()
            except ValueError:
                rel = ""
            status = goal_status.get(rel)
            try:
                if status == "proved":
                    backup.unlink()
                else:
                    shutil.copy2(backup, original)
                    backup.unlink()
                backups_handled += 1
            except OSError:
                pass

    # P0-#1 also sid-keys the .tmp staging file (see _skeleton.py:
    # `tmp = parent_abs.with_suffix(parent_abs.suffix + f".tmp_{sid_token}")`)
    # so daemon-crash mid-Verify can leak `.lean.tmp_s<id>` files. Glob
    # both the legacy plain suffix and the sid-suffixed variant —
    # missing the latter would let sid-keyed orphans accumulate forever.
    for pattern in ("**/*.lean.tmp", "**/*.lean.tmp_s*"):
        for tmp in problems_root.glob(pattern):
            try:
                tmp.unlink()
                tmps_removed += 1
            except OSError:
                pass

    return backups_handled, tmps_removed
