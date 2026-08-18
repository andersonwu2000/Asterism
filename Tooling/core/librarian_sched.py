"""Librarian five-stage chain scheduling — split out of dispatcher.py (task #9).

A complete second scheduler (the dedup -> classify -> migrate -> cleanup ->
bridge per-file DAG, the `` per-file target encoding, the persistent
fail-count / STALL policy, selfstart, and the harvest-outstanding backstop)
lived inside the 2.2k-line dispatcher module. The dispatcher now imports it;
`dispatcher._derive_librarian_work` etc. remain as re-exports, so call sites,
tests and operator runbooks keep their historical names. Pure move — no
behavior change; docstrings and incident notes travel with their functions.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..state import db

LIBRARIAN_MAX_CHAIN_RETRIES = 2


def _librarian_index_has(conn, problem: str) -> bool:
    """True iff `problem`'s bridge/Gate B already PASSED — the idempotent
    'finish done' marker, distinguishing 'all cleaned, bridge pending' from
    'finished'. v18: the marker is `problems.library_bridged_at` (was: a
    `## <problem>` section string-matched in Library/INDEX.md — the one
    librarian checkpoint that lived outside the DB; task #4)."""
    return db.problem_library_bridged(conn, problem)


def _librarian_invalidate_index(conn, problem: str) -> None:
    """Clear `problem`'s stale done-marker when it is being RE-cleaned
    (already promoted, but its Library is now being rewritten). Without this
    the stale marker reads as 'finished' (`_derive_librarian_work`) and the
    terminal bridge/Gate B is skipped — the re-cleaned Library would be
    re-exposed without re-verifying. Clearing it makes bridge re-fire +
    re-promote."""
    if db.problem_library_bridged(conn, problem):
        db.clear_library_bridged(conn, problem)
        print(f"[librarian] {problem}: re-clean detected → cleared stale "
              f"bridge marker (bridge/Gate B will re-verify + re-promote)",
              flush=True)


# #92 — a Librarian queue row for the parallel phases (migrate/cleanup) encodes
# its target FILE in the target_id as `problem\x1ffile`, so the generic pop /
# running-dedup / submit machinery treats each file as a distinct unit (the
# running key (target_id, kind, decision_id) is naturally per-file) with NO
# change to that machinery. Phase steps (dedup/classify/bridge) stay a plain
# `problem` target_id. Only Librarian-aware code decodes; proving target_ids are
# goal ints and never contain the separator, so they are unaffected.
_LIB_SEP = "\x1f"


def _lib_encode(problem: str, target_file: str) -> str:
    return f"{problem}{_LIB_SEP}{target_file}"


def _lib_decode(target_id: str) -> "tuple[str, str | None]":
    """`problem\\x1ffile` → (problem, file); a plain `problem` → (problem, None)."""
    if _LIB_SEP in target_id:
        problem, target_file = target_id.split(_LIB_SEP, 1)
        return problem, target_file
    return target_id, None


def _derive_librarian_work(
    conn: sqlite3.Connection, problem: str, workspace: Path,
) -> tuple[str | None, str | None]:
    """Derive the next Librarian work_kind from library_decls state
    (plan §5). Pure read. Returns (work_kind, target):

      - no rows                        → ('dedup', None)   [mechanical keep-all]
      - any 'candidate' (un-verdicted) → ('dedup', None)   [defensive]
      - any 'deduped' (kept, unplaced) → ('classify', None)
      - any 'classified'               → ('migrate', <next ready file>)
      - any 'migrated', not bridged    → ('bridge', None)  [v0.3: no cleanup]
      - otherwise (terminal + done)    → (None, None)

    v0.3 (plan §3): `dedup` is the mechanical keep-all (`_run_keepall`, no
    agent); cleanup is removed — `migrated` goes straight to the bridge Gate B
    probe. The `cleaned` lifecycle is no longer produced.

    bridge (Gate B, plan §2) is the terminal step: once every file is
    'migrated' it re-derives the original root from the Library and, on
    success, sets the bridge marker (`problems.library_bridged_at`) — the
    single done-marker; a Library that fails to re-derive never 'finishes'.

    migrate's target is a Library FILE, not a slug — the parallel unit is
    the whole file (plan §5 Step 3). `next_migrate_file` picks a file whose
    dependency files are all already migrated (topological order over the
    reconstructed file DAG); the re-enqueue chain advances the rest. bridge
    is gated on the bridge marker so it fires once, not in a loop."""
    rows = db.library_decls_for(conn, problem)
    if not rows:
        return ("dedup", None)
    by_state: dict[str, list] = {}
    for r in rows:
        by_state.setdefault(str(r["lifecycle"]), []).append(r)
    if by_state.get("candidate"):
        return ("dedup", None)
    if by_state.get("deduped"):
        return ("classify", None)
    if by_state.get("classified"):
        from ..pipeline import librarian
        return ("migrate", librarian.next_migrate_file(
            conn, problem=problem, workspace=workspace))
    # v0.4 (plan §10/§11, §13 3c-2): once all files are migrated, the cleanup-
    # dedup stage runs PER FILE (advances migrated → cleaned/dropped) BEFORE the
    # bridge Gate B probe. Like migrate it is a per-file phase — `_librarian_
    # refill` enqueues ready files (`ready_cleanup_files`) and the plain `problem`
    # row is a no-op; the `None` target signals "per-file phase" here. Bridge
    # then sets the bridge marker (= promote / done-marker).
    if by_state.get("migrated"):
        return ("cleanup", None)
    if by_state.get("cleaned") and not _librarian_index_has(conn, problem):
        return ("bridge", None)
    return (None, None)


def _advance_librarian_chain(
    conn: sqlite3.Connection, workspace: Path, target_id: str, *,
    outcome: str, reason: str, fail_counts: dict, pipeline_id: str = "",
) -> None:
    """Per-unit fail tracking for the Librarian chain (#92).

    Re-enqueue is owned by the tick-level `_librarian_refill` (the DAG
    scheduler) — here we only COUNT failures so a unit that keeps failing is
    skipped (stalled) by the refill instead of looping forever. `target_id` is
    the finished row's queue id: a plain `problem` (serial phase step) or
    `problem\\x1ffile` (per-file migrate/cleanup unit). Mutates `fail_counts`,
    keyed by `target_id` so each file/phase stalls independently. Surviving a
    transient gateway/harness failure: the refill re-enqueues the same unit
    next tick until the count crosses `LIBRARIAN_MAX_CHAIN_RETRIES`."""
    if outcome in ("success", "proved"):
        fail_counts.pop(target_id, None)
        db.clear_librarian_fail_count(conn, target_id=target_id)   # write-through
        return
    if reason == "librarian_file_busy":
        # Transient same-path contention (the lock holder needs minutes, the
        # loser's retries land in seconds) — re-enqueued by the refill, but
        # NOT a strike against the unit: counting it burned the cap before
        # the winner finished (2026-06-11).
        print(f"[librarian] {target_id.split(chr(31))[0]}: unit busy "
              f"(same-path migrate in flight) — will retry, not counted",
              flush=True)
        return
    n = fail_counts.get(target_id, 0) + 1
    fail_counts[target_id] = n
    db.set_librarian_fail_count(conn, target_id=target_id, n=n)    # survives restart
    problem, target_file = _lib_decode(target_id)
    unit = target_file or "chain step"
    if n > LIBRARIAN_MAX_CHAIN_RETRIES:
        # Surface the real error inline. The rich `failure_detail` lives in
        # dead_attempts keyed by pipeline_id (Librarian records it under
        # target_id=0, so it can't be found by problem/file) — without this it
        # was only diggable by hand (hit 5x this session).
        detail = ""
        if pipeline_id:
            try:
                row = conn.execute(
                    "SELECT failure_detail FROM dead_attempts "
                    "WHERE pipeline_id=? ORDER BY id DESC LIMIT 1",
                    (pipeline_id,)).fetchone()
                if row and row[0]:
                    detail = " — " + str(row[0]).strip().splitlines()[0][:200]
            except sqlite3.Error:
                pass
        print(f"[librarian] {problem}: unit `{unit}` STALLED after {n} "
              f"failures ({reason}){detail} — needs operator", flush=True)
    else:
        print(f"[librarian] {problem}: unit `{unit}` failed ({reason}); "
              f"will retry (attempt {n}/{LIBRARIAN_MAX_CHAIN_RETRIES})",
              flush=True)


def _librarian_selfstart_problems(
    conn: sqlite3.Connection, workspace: Path,
    intents, *, scope: str | None,
) -> "list[str]":
    """In-scope problems whose Librarian chain should START this run but has
    no durable trigger left (#92 Bug B): opted-in (the `library` setting),
    Ingest committed, no INDEX yet, and no `library_decls` rows (chain never
    began, or the library was reset). The one-shot enqueue (approve-ingest,
    or `_commit_ingest` under direct-ingest config) is wiped by
    `recover_at_startup`'s blanket queue clear, so the refill self-seeds
    `dedup` for these, making the daemon resume Library-ization across a
    restart instead of stranding it.

    Phase 6 — eligibility is `problems.ingested_at` (the Strategist's
    committed terminal judgment), replacing the old root-proved+integrity
    selector: harvest is strictly Ingest-driven and pure-NL problems have
    no root to key on. Soundness ordering is preserved — the Ingest verify
    gate already requires a present root to be `proved` (and
    `root_integrity_gate` still runs its axiom probe on proving), and the
    harvest-side per-decl axiom re-gates (6cb7d48) cover the deliverable
    closure independently of the root. Gated on the per-problem
    `library: true` opt-in (default False), so this never
    auto-Library-izes an unmarked problem."""
    if scope:
        ingested = conn.execute(
            "SELECT name AS problem FROM problems"
            " WHERE ingested_at IS NOT NULL AND name LIKE ?",
            (scope,)).fetchall()
    else:
        ingested = conn.execute(
            "SELECT name AS problem FROM problems"
            " WHERE ingested_at IS NOT NULL").fetchall()
    out: list[str] = []
    for (problem,) in ingested:
        if problem not in intents:
            continue
        if not intents[problem].library:
            continue
        # anchor+claim sign-off pause (2026-07-03): a Strategist `Ingest`
        # under `library.require_signoff` set `ingest_signoff_pending` and is
        # waiting for `asterism approve-ingest`. Do NOT auto-start the chain —
        # else this dispatcher path bypasses the human gate (MV run: the
        # trivial `main:True` root proving auto-started harvest while the
        # Ingest was paused). `approve-ingest` clears the flag + enqueues.
        if db.problem_ingest_signoff_pending(conn, problem):
            continue
        if _librarian_index_has(conn, problem):
            continue
        if db.library_decls_for(conn, problem):
            continue  # already has rows — driven by the library_decls path
        out.append(problem)
    return out


def _librarian_refill(
    conn: sqlite3.Connection, workspace: Path,
    running: "set[tuple]", intents, *, scope: str | None = None,
    fail_counts: dict,
) -> bool:
    """Tick-level DAG scheduler for the Librarian chain (#92) — the analogue of
    `bfs_refill` for proving. For every problem whose chain is active:

      - serial phase (dedup/classify/bridge): ensure ONE plain `problem`
        Librarian row is queued.
      - per-file phase (migrate/cleanup): enqueue one `problem\\x1ffile` row per
        READY file (its dep-files are all done, and it is neither in-flight nor
        already queued) so independent files run concurrently in the pool.

    Drives problems that already have `library_decls` rows PLUS opted-in
    proved problems with no chain yet (`_librarian_selfstart_problems`, Bug B)
    — so the daemon (re)starts and resumes Library-ization on its own, not just
    when the verify hook fires at proof time.

    Returns whether any LIVE Librarian work remains in scope (something was
    enqueued this tick, or a unit is in-flight / already queued). The
    workspace-exit gate uses this so the daemon does NOT quit with Library-ization
    pending — proof work alone no longer keeps it alive (Bug A). Units whose
    fail count crossed `LIBRARIAN_MAX_CHAIN_RETRIES` are skipped (stalled — they
    do NOT count as pending, so a fully-stalled chain lets the daemon exit for
    the operator to inspect)."""
    from ..pipeline import librarian
    if scope:
        prob_rows = conn.execute(
            "SELECT DISTINCT problem FROM library_decls WHERE problem LIKE ?",
            (scope,)).fetchall()
    else:
        prob_rows = conn.execute(
            "SELECT DISTINCT problem FROM library_decls").fetchall()
    problems = [p for (p,) in prob_rows]
    seen = set(problems)
    for p in _librarian_selfstart_problems(
            conn, workspace, intents, scope=scope):
        if p not in seen:
            problems.append(p)
            seen.add(p)

    pending = False
    for problem in problems:
        # Paused awaiting human ingest sign-off — don't drive the chain (belt
        # to selfstart's brace: a problem may already hold library_decls rows,
        # so skip it here too). Not counted as `pending`: the outstanding work
        # is the HUMAN's approve-ingest, not the daemon's — it may idle/exit.
        if db.problem_ingest_signoff_pending(conn, problem):
            continue
        work_kind, _ = _derive_librarian_work(conn, problem, workspace)
        if work_kind is None:
            continue
        # Re-cleaning an already-promoted problem: its INDEX entry is stale, and
        # `_derive_librarian_work` would read it as "done" after cleanup, skipping
        # the terminal bridge/Gate B. Invalidate it now (single-threaded tick) so
        # bridge re-fires once the rewritten Library is all cleaned.
        if work_kind == "cleanup" and _librarian_index_has(conn, problem):
            _librarian_invalidate_index(conn, problem)
        if work_kind in ("migrate", "cleanup"):
            # Both are per-file phases (#92 migrate, §13 3c-2 cleanup): enqueue
            # one `problem\x1ffile` row per READY file so independent files run
            # concurrently. The per-file row's step is resolved at run time by
            # `file_work_kind` (migrate while classified, cleanup once migrated),
            # so the two phases share the same encode/in-flight machinery.
            inflight: set[str] = set()
            for r in running:
                if r[1] != "Librarian":
                    continue
                rp, rf = _lib_decode(r[0])
                if rp == problem and rf is not None:
                    inflight.add(rf)
            queued = set()
            # v17: per-file units carry the file in `payload` JSON
            # (target_id is the plain problem) — the \x1f smuggle is
            # retired from the persisted rows. The composed
            # `problem\x1ffile` string remains the IN-PROCESS dispatch
            # identity (running keys, fail_counts — STATUS reset rule 2
            # unchanged), assembled by the dispatcher's pop loop.
            for (qf,) in conn.execute(
                    "SELECT json_extract(payload, '$.file') FROM queue"
                    " WHERE kind='Librarian' AND target_id = ?"
                    " AND payload IS NOT NULL", (problem,)):
                if qf:
                    queued.add(str(qf))
            skip = inflight | queued
            if skip:
                pending = True  # a file is mid-flight or already queued
            ready = (librarian.ready_file_work if work_kind == "migrate"
                     else librarian.ready_cleanup_files)
            for _wk, f in ready(
                    conn, problem=problem, workspace=workspace, in_flight=skip):
                tid = _lib_encode(problem, f)
                if fail_counts.get(tid, 0) > LIBRARIAN_MAX_CHAIN_RETRIES:
                    continue  # stalled file — operator
                db.enqueue(conn, kind="Librarian", target_id=problem,
                           target_kind="Problem", priority=0,
                           problem=problem, payload={"file": f})
                pending = True
        else:
            # Serial phase — a single plain `problem` row.
            if fail_counts.get(problem, 0) > LIBRARIAN_MAX_CHAIN_RETRIES:
                continue  # stalled — not pending, daemon may exit
            if (problem, "Librarian", None) in running:
                pending = True
                continue
            # no_payload: since v17 per-file rows share target_id=problem
            # (file rides payload) — this serial-phase dedup must only see
            # PLAIN rows or a queued file unit masks the serial step.
            if db.queue_contains(conn, kind="Librarian", target_id=problem,
                                 no_payload=True):
                pending = True
                continue
            db.enqueue(conn, kind="Librarian", target_id=problem,
                       target_kind="Problem", priority=0, problem=problem)
            pending = True
    return pending


def _harvest_outstanding(
    conn: sqlite3.Connection, workspace: Path, intents, *,
    scope: str | None, fail_counts: dict,
) -> bool:
    """Durable-state 'Library-ization still owed' guard for the workspace-exit
    gate — a timing-independent backstop for `librarian_pending`.

    `librarian_pending` (from `_librarian_refill`) is derived from the TRANSIENT
    queue/running/library_decls snapshot. On the proof→harvest handoff tick — the
    root just became integrity-verified and the mechanical `dedup` is completing
    in a worker thread — that snapshot can momentarily read "no live work", so the
    exit gate declares `all roots proved` and `_exit_pool_fast` kills the just-
    dispatched Librarian, SILENTLY skipping harvest on a cleanly-proved opted-in
    problem (observed 2026-06-29 on `pullback_flat_form`: root proved, axioms
    clean, 13 `deduped` decls, yet the daemon exited before `classify`). This guard
    depends only on DURABLE state — the INDEX done-marker, the committed
    `library_decls` lifecycle, and the persisted fail-count — so it stays True
    across that window regardless of in-flight timing.

    Returns True iff some in-scope problem is opted-in (the `library` setting),
    Ingest-committed (Phase 6 — same eligibility as
    `_librarian_selfstart_problems`; harvest is strictly Ingest-driven), has
    no Library INDEX yet, and its next Librarian step is NOT stalled (fail
    count past `LIBRARIAN_MAX_CHAIN_RETRIES`). A fully-stalled chain is NOT
    outstanding, preserving the "stalled chain lets the daemon exit for the
    operator to inspect" contract (`_librarian_refill` docstring)."""
    from ..pipeline import librarian
    if scope:
        rows = conn.execute(
            "SELECT name AS problem FROM problems"
            " WHERE ingested_at IS NOT NULL AND name LIKE ?",
            (scope,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT name AS problem FROM problems"
            " WHERE ingested_at IS NOT NULL").fetchall()
    for (problem,) in rows:
        if problem not in intents or not intents[problem].library:
            continue
        # Paused awaiting human ingest sign-off — this is HUMAN-outstanding, not
        # daemon-outstanding, so it must NOT hold the daemon alive. The human's
        # approve-ingest re-enqueues + clears the flag when they're ready.
        if db.problem_ingest_signoff_pending(conn, problem):
            continue
        if _librarian_index_has(conn, problem):
            continue  # harvest already complete (INDEX = the done-marker)
        work_kind, _target = _derive_librarian_work(conn, problem, workspace)
        if work_kind is None:
            continue  # nothing further derivable
        if work_kind in ("migrate", "cleanup"):
            ready = (librarian.ready_file_work if work_kind == "migrate"
                     else librarian.ready_cleanup_files)
            for _wk, f in ready(conn, problem=problem, workspace=workspace,
                                in_flight=set()):
                if fail_counts.get(
                        _lib_encode(problem, f), 0
                ) <= LIBRARIAN_MAX_CHAIN_RETRIES:
                    return True  # a ready file can still progress
        elif fail_counts.get(problem, 0) <= LIBRARIAN_MAX_CHAIN_RETRIES:
            return True  # serial step (dedup/classify/bridge) can still run
    return False


