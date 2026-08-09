"""Daemon-startup recovery — reconcile transient state from a crashed
prior daemon back to a consistent baseline.

Extracted from `dispatcher.py`. The dispatcher's main
loop concerns itself with steady-state work; FS↔DB reconciliation is
a structurally separate phase that runs once at startup.

Six classes of stale state, each restored:

  1. queue rows         — live dispatch state, never persists across
                          daemon lifetimes; cleared unconditionally.
  1b. 'running' pipelines rows (v38) — INSERTed at dispatch, finalized
                          at completion; a crashed daemon leaves them
                          'running' with no worker behind them. Marked
                          failed / outcome='daemon_crashed'
                          (scope-filtered; live concurrent drivers'
                          rows spared via the #90 owner-pid manifest).
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

import re
import shutil
import sqlite3
import subprocess
from pathlib import Path

from ..core.process_group import no_window_creationflags
from . import db
from . import proof_store


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


def _pipeline_problem(conn: sqlite3.Connection, target_id: str,
                      target_kind: str) -> "str | None":
    """Resolve a pipelines row's target to its problem name (for scope
    filtering), or None when the target no longer resolves. Mirrors the
    dispatcher's `_problem_of_target` shapes without importing core
    (state must stay import-clean of core): 'Problem' targets carry the
    name directly (Librarian per-file rows compose `problem\\x1ffile`),
    the rest resolve through their tables."""
    if target_kind == "Problem":
        return target_id.split("\x1f", 1)[0]
    try:
        tid = int(target_id)
    except (TypeError, ValueError):
        return None
    if target_kind == "Goal":
        row = conn.execute("SELECT problem FROM goals WHERE id = ?",
                           (tid,)).fetchone()
    elif target_kind == "Group":
        row = conn.execute("SELECT problem FROM groups WHERE id = ?",
                           (tid,)).fetchone()
    elif target_kind == "Strategy":
        row = conn.execute(
            "SELECT g.problem FROM strategies s"
            " JOIN goals g ON g.id = s.goal_id WHERE s.id = ?",
            (tid,)).fetchone()
    else:
        return None
    return str(row[0]) if row is not None else None


def recover_at_startup(conn: sqlite3.Connection,
                       workspace: Path | None = None,
                       scope: str | None = None) -> None:
    # Scope-safe queue clean-slate (v17 — the #74 fix): clear THIS scope's
    # unleased rows (refill re-derives them) plus this scope's rows whose
    # lease owner is provably dead (crashed prior run). Rows leased by a
    # LIVE owner belong to a concurrently-running dispatcher — leave them.
    # Unscoped (scope=None) still means "the whole workspace is mine", but
    # live leases are respected even then.
    from ..agent.sandbox import _pid_alive
    # Poison rows first, scope-blind: a row with an empty `problem`
    # belongs to NO scope, so the scoped clean below can never reach it
    # — which is how one survived every restart on 08-03 and, via
    # `is_in_queue`, suppressed T1+T4 for its group for 3h20m. Any
    # startup may delete them: they are undispatchable under every
    # scoped pop and re-derivable by whoever legitimately needs a wake.
    poison = conn.execute(
        "DELETE FROM queue WHERE problem IS NULL OR problem = ''"
    ).rowcount
    if poison:
        print(f"[dispatcher] recovery: swept {poison} POISON queue "
              f"row(s) with an empty problem — see the 2026-08-03 "
              f"stall post-mortem", flush=True)
    _scope_sql = "" if scope is None else " AND problem LIKE ?"
    _scope_args: tuple = () if scope is None else (scope,)
    queue_cleared = conn.execute(
        "DELETE FROM queue WHERE owner_pid IS NULL" + _scope_sql,
        _scope_args).rowcount
    for r in list(conn.execute(
            "SELECT id, owner_pid FROM queue WHERE owner_pid IS NOT NULL"
            + _scope_sql, _scope_args)):
        if not _pid_alive(r["owner_pid"]):
            conn.execute("DELETE FROM queue WHERE id = ?", (r["id"],))
            queue_cleared += 1

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
    # WORK ARTIFACT recorded (produced_goal_id for Forward's registered
    # lemma, produced_strategy_id for Backward's committed strategy) — the
    # worker reached its product, so outcome propagation fires from the
    # artifact's terminal and a second dispatch would just spawn a duplicate.
    # A Builder has no such artifact (it proves in place; produced_goal_id is
    # a commit-time backlink, not a work-done signal), so it is judged by its
    # target's status instead — see `db.null_inject_redispatch_specs`.
    #
    # The "which NULL-inject needs a worker + its queue spec" logic lives
    # in `db.null_inject_redispatch_specs`, shared with the per-tick
    # `dispatcher.reconcile_stuck_states` (which adds in-flight gating).
    # At startup the queue is clean (cleared above) so no gating is needed
    # here — re-enqueue every spec.
    # v17: scope-filtered (the unscoped form was #74's second half — a
    # scoped daemon's startup re-enqueued EVERY problem's NULL injects),
    # and routed through db.enqueue so the row carries its problem.
    inject_reenqueued = 0
    for spec in db.null_inject_redispatch_specs(conn, scope=scope):
        db.enqueue(conn, kind=spec["kind"], target_id=spec["target_id"],
                   target_kind=spec["target_kind"], priority=10,
                   decision_id=spec["decision_id"],
                   problem=spec["problem"])
        inject_reenqueued += 1

    # Never-woken groups — the one wake with no re-derivable trigger.
    # `_commit_delegate` queues the new group's Strategist seat
    # explicitly BECAUSE nothing else can find it: a fresh group has a
    # NULL clock (T1 reads that as "due a full interval after daemon
    # start"), no goals (no pending_review), and no batch (no
    # inject_batch_done). The unconditional queue clear above deletes
    # that one-shot row, and until 2026-08-08 nothing re-derived it —
    # a daemon restart landing between "group opened" and "first
    # dispatch" silently orphaned the group's launch, and the T4 stall
    # backstop picked it up 69 minutes later (g384, union_closed).
    # The predicate is derivable from the groups table alone: an active
    # SUB-group that never woke ⇒ its launch row is the one we just
    # cleared. Top groups are excluded — they are not born from a
    # Delegate and never had a launch row; their wakes belong to the
    # T1/stall selectors, and sweeping them in here woke every fresh
    # problem's Strategist at daemon start (caught by the e2e happy
    # path the same day this shipped).
    groups_relaunched = 0
    for r in conn.execute(
            "SELECT id, problem FROM groups"
            " WHERE status = 'active' AND last_strategist_at IS NULL"
            "   AND parent_group_id IS NOT NULL"
            + _scope_sql, _scope_args):
        db.enqueue(conn, kind="Strategist", target_id=str(r["id"]),
                   target_kind="Group", priority=10,
                   problem=str(r["problem"]))
        groups_relaunched += 1

    # v38 — stale 'running' pipeline rows. The dispatcher INSERTs the
    # pipelines row at dispatch time (status='running') and finalizes it
    # at completion; a daemon that died mid-pipeline leaves the row
    # 'running' with, by definition, no worker behind it. Finalize as
    # failed with the distinguishing outcome 'daemon_crashed' (vs the
    # worker-exception path's 'failed') so archaeology can tell "this
    # daemon watched it fail" from "a dead daemon abandoned it". The
    # per-retry attempts++/dead_attempts pairs were written eagerly
    # in-loop, so no forensic catch-up write is owed here — only the
    # status flip.
    # Scope-filtered (the #74 class); a row whose problem cannot be
    # resolved is left alone under a scoped run (can't prove it's ours)
    # and finalized by the next unscoped/owning start. Rows whose
    # .attempts/<pid>/ sandbox manifest names a LIVE owner belong to a
    # concurrent non-daemon driver/e2e (#90) — spared.
    pipelines_finalized = 0
    for r in list(conn.execute(
            "SELECT id, target_id, target_kind FROM pipelines"
            " WHERE status = 'running'")):
        problem = _pipeline_problem(
            conn, str(r["target_id"]), str(r["target_kind"]))
        if scope is not None:
            if problem is None or conn.execute(
                    "SELECT ? LIKE ?", (problem, scope)).fetchone()[0] != 1:
                continue
        if workspace is not None and _attempt_owner_alive(
                workspace / ".attempts" / str(r["id"])):
            continue
        conn.execute(
            "UPDATE pipelines SET status = 'failed',"
            " outcome = 'daemon_crashed', finished_at = ? WHERE id = ?",
            (db.now(), r["id"]))
        pipelines_finalized += 1

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
    orphans_swept = 0
    orphans_kept_cited = 0
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

        # Orphan proof-file sweep (rule 10 — DB↔file paired): a Backward
        # placement that died before its goal-row commit leaves a
        # sorry-bearing stub with no row; uncited ones are deleted, cited
        # ones (already-propagated fake-proof) are logged for repair.
        orphans_swept, orphans_kept_cited = sweep_orphan_proof_files(
            conn, workspace, scope=scope)

    # Interrupted-cascade repair (task #11 crash-window audit): a live
    # `proposed` strategy under a hard-terminal goal is a cascade that died
    # between the goal flip and the sibling sweep (windows A3/F3/F4) — the
    # completed-cascade outcome is unambiguous (proved parent → superseded;
    # killed parent → dead), so finish the walk here. Per-row through the
    # checked mutator so the inject-outcome hook fires (D6 lesson).
    from . import consistency as _consistency
    _consistency.repair_unambiguous(conn)

    if (queue_cleared or inject_reenqueued or groups_relaunched
            or pipelines_finalized or strategies_killed
            or goals_reopened or goals_attempting_fixup
            or attempts_cleared or attempts_live_skipped
            or backups_handled or tmps_removed
            or patches_salvaged or probes_removed
            or orphans_swept or orphans_kept_cited):
        print(f"[dispatcher] recovery: cleared {queue_cleared} queue rows, "
              f"re-enqueued {inject_reenqueued} in-flight Inject pipelines, "
              f"relaunched {groups_relaunched} never-woken group(s), "
              f"finalized {pipelines_finalized} crashed 'running' "
              f"pipeline row(s), "
              f"killed {strategies_killed} half-baked strategies, "
              f"reopened {goals_reopened} stuck goals, "
              f"flipped {goals_attempting_fixup} open->attempting "
              f"(orphan-success fixup), "
              f"salvaged {patches_salvaged} orphan patches, "
              f"removed {attempts_cleared} orphan attempts dirs "
              f"(spared {attempts_live_skipped} live), "
              f"handled {backups_handled} lean backups, "
              f"removed {tmps_removed} stale .tmp files, "
              f"swept {probes_removed} stale migrate probes, "
              f"swept {orphans_swept} orphan proof files "
              f"(kept {orphans_kept_cited} cited — need repair)",
              flush=True)


_PROOF_IMPORT_RE = re.compile(
    r"^\s*import\s+(Problems\.[\w.]+\.proofs\.[A-Za-z_]\w*)\s*$",
    re.MULTILINE,
)


def _git_untracked_under(workspace: Path, rel_dir: str) -> set[str] | None:
    """Repo-relative posix paths of git-UNTRACKED (not committed, not
    ignored) files under `rel_dir`, or None if `workspace` is not a git
    repo (e.g. a unit-test tmp dir — nothing is committed there, so the
    caller treats every candidate as untracked).

    The orphan sweep MUST restrict deletion to untracked files: a genuine
    killed-placement orphan was never committed, whereas a *committed*
    proof file can also lack a current DB row (its problem's DB was
    reset / re-migrated while git kept the proofs). Deleting those is
    destroying committed work — a `git ls-files --others` gate is what
    separates the two. On a git error inside a real repo, return an empty
    set (protect everything — delete nothing) rather than risk it."""
    if not (workspace / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(workspace), "ls-files", "--others",
             "--exclude-standard", "--", rel_dir],
            capture_output=True, text=True, timeout=30, check=True,
            creationflags=no_window_creationflags(),
        ).stdout
        return {ln.strip() for ln in out.splitlines() if ln.strip()}
    except Exception:  # noqa: BLE001 — repo present but git failed → protect all
        return set()


def sweep_orphan_proof_files(conn: sqlite3.Connection, workspace: Path, *,
                             scope: str | None = None) -> tuple[int, int]:
    """Delete orphan proof files — `proofs/L_<slug>.lean` /
    `_strategy_s<id>.lean` present on disk, git-UNTRACKED, and backed by
    NO DB row.

    Orphans form when a Backward placement writes a sub-goal stub
    (backward.py `dest.write_text`) and the worker/daemon dies before the
    goal-row commit. That window is WIDE — it spans the per-file lake
    verify — and a hard kill / quota-exit / crash skips the Python
    failure-cleanup `unlink`, so the stub file survives with no row. The
    stub is `:= by sorry`; if a later proof cites it the sorry propagates
    silently to the root (P13 density_form_supp_lhs_slice → root sorryAx,
    invisible because an orphan has no tree node). Sweeping at startup —
    before any dispatch, so no live worker's freshly-placed file is at
    risk — restores the rule-10 DB↔file invariant.

    THREE guards keep this safe:
      - `scope`: only problems matching the daemon's scope are swept (a
        scoped run must never touch another problem's files).
      - git-UNTRACKED only (`_git_untracked_under`): a committed proof
        file can lack a current DB row (reset/migrated problem) — those
        are tracked, so they're protected; only never-committed
        placement-orphans are deletable.
      - cited-import guard: an orphan IMPORTED by another proof is kept
        and logged loudly (deleting it would break the importer's build —
        it signals an already-propagated fake-proof needing explicit
        repair). Returns (deleted, kept_cited).
    """
    deleted = 0
    kept_cited = 0
    problems = [r["problem"] for r in conn.execute(
        "SELECT DISTINCT problem FROM goals"
        + (" WHERE problem LIKE ?" if scope else ""),
        ((scope,) if scope else ()))]
    for problem in problems:
        proofs_dir = db.problem_dir(workspace, problem) / "proofs"
        if not proofs_dir.exists():
            continue
        untracked = _git_untracked_under(
            workspace, (proofs_dir.relative_to(workspace)).as_posix())
        known: set[str] = set()
        for r in conn.execute(
                "SELECT lean_path AS p FROM goals WHERE problem = ?"
                " AND lean_path IS NOT NULL", (problem,)):
            known.add(str(r["p"]))
        for r in conn.execute(
                "SELECT s.lean_path AS lp, s.scratch_path AS sp"
                " FROM strategies s JOIN goals g ON g.id = s.goal_id"
                " WHERE g.problem = ?", (problem,)):
            if r["lp"]:
                known.add(str(r["lp"]))
            if r["sp"]:
                known.add(str(r["sp"]))
        files = (sorted(proofs_dir.glob("L_*.lean"))
                 + sorted(proofs_dir.glob("_strategy_s*.lean")))
        # Modules imported by ANY proof file → the "cited" set.
        imported: set[str] = set()
        for f in files:
            try:
                t = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            imported.update(_PROOF_IMPORT_RE.findall(t))
        for f in files:
            rel = f.relative_to(workspace).as_posix()
            if rel in known:
                continue
            # Protect committed proofs: only git-untracked files are
            # genuine placement-orphans. (untracked is None → not a repo,
            # e.g. tests → treat all as untracked.)
            if untracked is not None and rel not in untracked:
                continue
            module = rel.removesuffix(".lean").replace("/", ".")
            if module in imported:
                kept_cited += 1
                print(f"[recovery] ORPHAN PROOF FILE STILL CITED — NOT "
                      f"deleting {rel}: no DB row but imported by a sibling. "
                      f"A fake-proof has propagated; needs explicit repair "
                      f"(reopen the importer chain).", flush=True)
                continue
            # Route through the proof_store chokepoint (not a raw `f.unlink`)
            # so EVERY proofs/ deletion is centralized + ownership-guarded +
            # lint-visible (2026-07-03). owner_goal_id=None: this is an orphan
            # (no DB row per the `known` filter above). `assert_writable`
            # double-checks no goal owns it — if the `known` set was stale and
            # the file IS owned, `ClobberError` fires and we SKIP the delete
            # rather than sweep a committed proof (the failed-cleanup-deletes-
            # a-committed-stub drift this chokepoint exists to prevent).
            try:
                proof_store.remove_proof(
                    conn, workspace, rel_path=rel, owner_goal_id=None)
                deleted += 1
                print(f"[recovery] swept orphan proof file (no DB row, "
                      f"uncited): {rel}", flush=True)
            except proof_store.ClobberError:
                print(f"[recovery] orphan-sweep SKIPPED {rel}: a goal owns it "
                      f"after all (stale known-set) — not deleting a committed "
                      f"proof", flush=True)
            except OSError:
                pass
    return deleted, kept_cited


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
