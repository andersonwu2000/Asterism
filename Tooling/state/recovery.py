"""Daemon-startup recovery — reconcile transient state from a crashed
prior daemon back to a consistent baseline.

Extracted from `dispatcher.py`. The dispatcher's main
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


def _attempt_owner_alive(attempt_dir: Path) -> bool:
    """True iff `<attempt_dir>/sandbox/_manifest.json` names a still-live
    `owner_pid`. A missing / unparseable manifest or a dead pid → False
    (treat as a genuine orphan, safe to clean).

    #90: the startup sweep must spare in-flight spawns owned by a
    concurrent NON-daemon driver/e2e — the singleton lock only fences
    other daemons, so a driver sharing this workspace's `.attempts/`
    would otherwise have its live spawn dirs nuked. Every SpawnWorkspace
    records its `owner_pid` here, so a per-dir liveness check distinguishes
    a live spawn from a crashed-run orphan. Errs toward preservation (any
    doubt → reported alive=False only when we can prove the owner is gone)."""
    import json
    from ..agent.sandbox import MANIFEST_NAME, _pid_alive
    manifest = attempt_dir / "sandbox" / MANIFEST_NAME
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return _pid_alive(data.get("owner_pid"))


def recover_at_startup(conn: sqlite3.Connection,
                       workspace: Path | None = None) -> None:
    queue_cleared = conn.execute("DELETE FROM queue").rowcount

    # Phase 2.5 — re-enqueue dispatch rows for any in-flight Inject
    # decisions whose outcome is still NULL. Forward queue rows in
    # particular only come from Strategist Inject commits; if the
    # daemon crashes between commit and dispatch (or between dispatch
    # and cascade), the queue row is gone forever and the batch never
    # completes — inject_batch_done never fires, daemon idle-exits
    # next run.
    #
    # Per-kind re-enqueue (residue_thm 2026-05-21 — previously the
    # re-enqueue was hardcoded as 'Forward' regardless of payload.
    # pipeline, so an Inject(Backward) caught mid-flight by a daemon
    # restart was redispatched as Forward, feeding the Backward brief
    # into a Forward worker and producing a nonsense lemma):
    #
    #   - payload.pipeline = "Forward" → ('Forward', problem, 'Problem')
    #   - payload.pipeline = "Backward" or "Builder" → (pipeline,
    #     target_goal_id, 'Goal')
    #
    # Skip the re-enqueue when the decision already has its produced
    # artifact recorded (produced_goal_id for Forward / Builder,
    # produced_strategy_id for Backward) — the worker has committed,
    # so outcome propagation will fire from the artifact's terminal,
    # and a second dispatch would just spawn a duplicate worker.
    import json as _json
    inject_reenqueued = 0
    for r in conn.execute(
        "SELECT id, problem, payload, target_id, produced_goal_id,"
        " produced_strategy_id FROM strategist_decisions"
        " WHERE decision_kind = 'Inject' AND outcome IS NULL"
    ).fetchall():
        try:
            payload = _json.loads(r["payload"] or "{}")
        except (_json.JSONDecodeError, TypeError):
            payload = {}
        pipeline = payload.get("pipeline")
        if pipeline == "Forward":
            if r["produced_goal_id"] is not None:
                continue  # Forward already produced a lemma; outcome
                          # propagates from goal terminal.
            conn.execute(
                "INSERT INTO queue (kind, target_id, target_kind, priority,"
                " decision_id, created_at) VALUES"
                " ('Forward', ?, 'Problem', 10, ?, ?)",
                (str(r["problem"]), int(r["id"]), db.now()),
            )
            inject_reenqueued += 1
        elif pipeline in ("Backward", "Builder"):
            target_id = r["target_id"]
            if target_id is None:
                continue  # malformed row — payload says Backward/
                          # Builder but no target_goal_id. Skip rather
                          # than dispatch into the void.
            if pipeline == "Backward" and r["produced_strategy_id"] is not None:
                continue  # Backward already committed a strategy;
                          # outcome propagates from strategy terminal.
            if pipeline == "Builder" and r["produced_goal_id"] is not None:
                continue  # Builder already wrote the goal stub;
                          # outcome propagates from goal terminal.
            conn.execute(
                "INSERT INTO queue (kind, target_id, target_kind, priority,"
                " decision_id, created_at) VALUES"
                " (?, ?, 'Goal', 10, ?, ?)",
                (pipeline, str(int(target_id)), int(r["id"]), db.now()),
            )
            inject_reenqueued += 1
        # Unknown pipeline (legacy / malformed) — skip silently. The
        # decision remains outcome=NULL and will surface on the next
        # Strategist context as a stale-batch indicator.

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

    # Inverse reconciliation — goals stuck at 'open' despite having a
    # live 'proposed' strategy. Daemon shutdown races leave this
    # state behind: a Backward worker writes its strategy row + records
    # the pipeline as 'succeeded' AFTER the main thread's
    # `pool.shutdown(wait=False)` has returned (quota self-exit at
    # `dispatcher.py`'s consec_spawn_fail trip path is the canonical
    # trigger). The cascade callback that would have flipped the goal
    # to 'attempting' never runs because the main loop is gone, and
    # the next daemon's bfs_refill sees the goal as 'open' and
    # dispatches a duplicate Backward — producing N parallel live
    # strategies on the same goal with overlapping intent.
    # Symptom from residue_thm 2026-05-21: g2458 had s10596 and
    # s10609 both 'proposed' after daemon 023003 quota-died mid-pipe.
    goals_attempting_fixup = conn.execute(
        "UPDATE goals SET status = 'attempting', updated_at = ?"
        " WHERE status = 'open'"
        "   AND EXISTS ("
        "     SELECT 1 FROM strategies"
        "     WHERE goal_id = goals.id AND status = 'proposed'"
        "   )",
        (db.now(),),
    ).rowcount

    conn.commit()

    attempts_cleared = 0
    attempts_live_skipped = 0
    backups_handled = 0
    tmps_removed = 0
    patches_salvaged = 0
    probes_removed = 0
    if workspace is not None:
        # Patch salvage FIRST — capture orphan patch.lean bodies
        # before the rmtree pass drops them. Hard-kill of daemon
        # (user Stop-Process, OS crash) leaves workers' in-flight
        # proofs in .attempts/<uuid>/patch.lean; the postmortem
        # path only fires on watchdog timeouts. Salvage extracts
        # the theorem name, maps to the goal, persists under
        # `.drafts/<kind>_g<gid>_patch.lean`; next Builder dispatch
        # surfaces via context._section_prior_patch.
        try:
            from ..pipeline import _drafts as _drafts_mod
            patches_salvaged = _drafts_mod.salvage_orphan_patches(
                conn, workspace)
        except Exception as e:  # noqa: BLE001 — best-effort
            print(f"[dispatcher] patch salvage skipped: {e}", flush=True)

        attempts_root = workspace / ".attempts"
        if attempts_root.exists():
            for d in attempts_root.iterdir():
                if not d.is_dir():
                    continue
                # #90 — spare a live spawn's dir owned by a concurrent
                # non-daemon driver/e2e; only nuke genuine orphans (the
                # singleton lock already fences other daemons).
                if _attempt_owner_alive(d):
                    attempts_live_skipped += 1
                    continue
                try:
                    shutil.rmtree(d)
                    attempts_cleared += 1
                except OSError:
                    pass  # claude subprocess may still hold a handle

        backups_handled, tmps_removed = sweep_lean_backups(conn, workspace)

        # Stale Library/_migrate_probe_* (#104): the Librarian Gate B /
        # migrate verify writes a temp probe under Library/ and unlinks
        # it in a `finally` — but a hard kill (Stop-Process / power loss)
        # mid-verify skips the finally, orphaning the probe in the
        # curated Library/, where it pollutes the import closure and the
        # next inventory. The prefix is framework-owned, so sweeping it is
        # always safe. Best-effort.
        libdir = workspace / "Library"
        if libdir.exists():
            for p in libdir.glob("_migrate_probe_*"):
                try:
                    p.unlink()
                    probes_removed += 1
                except OSError:
                    pass

    if (queue_cleared or inject_reenqueued or strategies_killed
            or goals_reopened or goals_attempting_fixup
            or attempts_cleared or attempts_live_skipped
            or backups_handled or tmps_removed
            or patches_salvaged or probes_removed):
        print(f"[dispatcher] recovery: cleared {queue_cleared} queue rows, "
              f"re-enqueued {inject_reenqueued} in-flight Inject Forwards, "
              f"killed {strategies_killed} half-baked strategies, "
              f"reopened {goals_reopened} stuck goals, "
              f"flipped {goals_attempting_fixup} open->attempting "
              f"(orphan-success fixup), "
              f"salvaged {patches_salvaged} orphan patches, "
              f"removed {attempts_cleared} orphan attempts dirs "
              f"(spared {attempts_live_skipped} live), "
              f"handled {backups_handled} lean backups, "
              f"removed {tmps_removed} stale .tmp files, "
              f"swept {probes_removed} stale migrate probes",
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
      - If no goal row references this lean_path, the operator wiped
        state (`cli reset` / DB drop) but the backup survived because
        the reset glob didn't cover this suffix variant. Restoring
        would resurrect a goal-less .lean orphan with the original
        mtime — observed SG 2026-05-18: `.verify_backup_s9983`
        survived reset, sweep restored a sorry-bearing
        `L_three_reals_pigeonhole_sign.lean`, then Strategist
        injected a dependent decomposition that silently `have`'d the
        unproven sorry. Discard the backup.
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

    # Sid-keyed backups (`.lean.verify_backup_s<id>`) ensure
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
                if status == "proved" or status is None:
                    backup.unlink()
                else:
                    shutil.copy2(backup, original)
                    backup.unlink()
                backups_handled += 1
            except OSError:
                pass

    # The .tmp staging file is also sid-keyed (see _skeleton.py:
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
