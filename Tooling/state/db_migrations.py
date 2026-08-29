"""state.db_migrations — additive column backfills + user_version
stepping, split out of db.py at the v24 schema rework (the file-size
ratchet's documented natural cut). Runs on every init_schema call;
each step is idempotent. New steps append here, and the version pin
tests (test_db_phase7 / test_phase2_migration) assert the terminal
user_version."""
from __future__ import annotations

import contextlib
import os
import re
import sqlite3
from pathlib import Path

from .db import now


@contextlib.contextmanager
def _migration_mutex(conn: sqlite3.Connection):
    """ONE migrator at a time, cross-process. `connect()` auto-migrates
    on every stale connection and a daemon boot opens several (main +
    gateway subprocess + serve): two racers both built `_sd_v43` and
    the loser took the daemon down 4s after start (2026-08-24, the
    first live v43 run — WAL does not defend schema-level races, rule
    3). A sqlite transaction cannot be the mutex here: helpers commit
    mid-ladder and `executescript` implicitly commits, either of which
    would silently release it. An OS file lock beside the DB has no
    such seams. In-memory DBs are single-process; they skip the lock."""
    row = conn.execute("PRAGMA database_list").fetchone()
    dbfile = row[2] if row else ""
    if not dbfile:
        yield
        return
    lock_path = dbfile + ".migrate.lock"
    f = open(lock_path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    continue  # LK_LOCK gives up after ~10s; keep waiting
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()

# v21 (frontend charter §5-2) — per-spawn token/turn accounting. Created
# in the migration chain (fresh DBs start at user_version 0 and run the
# whole chain, so SCHEMA does not duplicate it).
_SPAWN_USAGE_DDL = """
CREATE TABLE IF NOT EXISTS spawn_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id   TEXT NOT NULL,
    kind          TEXT NOT NULL,
    problem       TEXT,
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_new_tokens  INTEGER NOT NULL DEFAULT 0,
    turns         INTEGER NOT NULL DEFAULT 0,
    wall_sec      REAL,
    ts            TEXT NOT NULL
)
"""


def apply(conn: sqlite3.Connection) -> None:
    """Bring an existing DB up to the current schema version."""
    with _migration_mutex(conn):
        _apply_locked(conn)


def _apply_locked(conn: sqlite3.Connection) -> None:
    """The ladder proper — every version read happens INSIDE the
    mutex, so a waiter re-reads the winner's bump and no-ops."""
    # Read the incoming version FIRST: the additive loop below must not
    # resurrect columns a later versioned migration DROPPED (v33 drops
    # goals.entry_kind; the unconditional ALTER re-added it on every
    # daemon start — review 07-27 #4).
    v0 = conn.execute("PRAGMA user_version").fetchone()[0]
    # Additive migrations for older DBs (CREATE TABLE IF NOT EXISTS is
    # a no-op when the table already exists, so blind ALTER TABLE is
    # needed to backfill columns added in later versions). Idempotent
    # via "duplicate column name" detection.
    for col, ddl in (
        # Routine-only Strategist clock (T1 fires on its own cadence; see the
        # SCHEMA comment on problems.last_routine_at). Additive nullable
        # column — no user_version bump needed (same pattern as bootstrap_done
        # / strategist_directive).
        ("last_routine_at",
         "ALTER TABLE problems ADD COLUMN last_routine_at TEXT NULL"
         " DEFAULT NULL"),
        ("alias_target_id",
         "ALTER TABLE goals ADD COLUMN alias_target_id INTEGER NULL"
         " DEFAULT NULL REFERENCES goals(id)"),
        # Migration entry for older DBs created before entry_kind landed.
        # The CREATE TABLE above already declares this column with a
        # CHECK constraint; this ALTER picks up disk DBs created prior
        # and adds the column with the same NOT NULL default. SQLite
        # ALTER TABLE can't add CHECK after the fact; the CHECK is only
        # enforced for new DBs, but `insert_goal` is the only writer of
        # this column and it always passes a validated value.
        ("entry_kind",
         "ALTER TABLE goals ADD COLUMN entry_kind TEXT NOT NULL"
         " DEFAULT 'Builder'"),
        # See SCHEMA comment on `goals.integrity_verified` for rationale.
        # New rows default to 0; backfill below promotes pre-migration
        # proved roots to 1.
        ("integrity_verified",
         "ALTER TABLE goals ADD COLUMN integrity_verified INTEGER NOT NULL"
         " DEFAULT 0"),
        # Phase 2 — problems columns. Pure ADD COLUMN (no CHECK extension
        # on existing columns); idempotent. See `docs/archive/design/phase2/pipelines.md`
        # §4.1 for semantics.
        ("bootstrap_done",
         "ALTER TABLE problems ADD COLUMN bootstrap_done INTEGER NOT NULL"
         " DEFAULT 0 CHECK(bootstrap_done IN (0,1))"),
        ("strategist_directive",
         "ALTER TABLE problems ADD COLUMN strategist_directive TEXT"
         " NULL DEFAULT NULL"),
        ("last_strategist_at",
         "ALTER TABLE problems ADD COLUMN last_strategist_at TEXT"
         " NULL DEFAULT NULL"),
        # Phase 2.5 — Strategist multi-Inject batch grouping. Same UUID
        # across all Inject rows committed in one briefs-list decision
        # (every Inject is a batch under the unified schema; N=1 is
        # degenerate). Cascade fires Strategist with
        # trigger_kind='inject_batch_done' when the last Forward in
        # the batch finishes. Pure ADD COLUMN (no CHECK on this column);
        # the CHECK widening for trigger_kind happens via
        # _migrate_to_phase3 below.
        ("batch_id",
         "ALTER TABLE strategist_decisions ADD COLUMN batch_id TEXT"
         " NULL DEFAULT NULL"),
        # Phase 2.5 evolution — Inject decision's "completion" was
        # originally filled when the Forward agent finished writing
        # (sorry-bearing or otherwise). That caused inject_batch_done
        # to fire while produced lemmas were still `:= by sorry`,
        # leading Strategist to Reopen parent goals whose new deps
        # were unproven and Backward to leaf-bypass-cite them →
        # sorryAx rollback (observed residue_thm 2026-05-19, goals
        # 1741 / 1768 / 1759 / 1753). The fix shifts "completion" to
        # "produced lemma reached a terminal status (proved /
        # shelved / disproved)" — the Inject decision tracks the
        # goal it produced via `produced_goal_id` and its `outcome`
        # is filled when that goal terminates, not when the agent
        # finishes. Pure ADD COLUMN, no CHECK to widen.
        ("produced_goal_id",
         "ALTER TABLE strategist_decisions ADD COLUMN produced_goal_id"
         " INTEGER NULL DEFAULT NULL"
         " REFERENCES goals(id) ON DELETE SET NULL"),
        # Inject(Backward/Builder) outcome-tracking — see the column
        # comment in SCHEMA above. Closes the Strategist wake-up
        # asymmetry where only Forward batches fired `inject_batch_
        # done`.
        ("produced_strategy_id",
         "ALTER TABLE strategist_decisions ADD COLUMN produced_strategy_id"
         " INTEGER NULL DEFAULT NULL"
         " REFERENCES strategies(id) ON DELETE SET NULL"),
        # #4 — rich terminal-decline reasoning (Forward `## Why` etc.) so
        # the Strategist sees WHY its brief was declined, not just the
        # coarse `outcome` enum. Additive nullable — no user_version bump.
        ("outcome_detail",
         "ALTER TABLE strategist_decisions ADD COLUMN outcome_detail TEXT"
         " NULL DEFAULT NULL"),
        # anchor+claim architecture — top-level deliverable marker set by
        # the Strategist. Additive defaulted (CHECK only enforced for
        # fresh DBs; `mark_deliverable` is the sole writer and passes
        # 0/1). No user_version bump (same pattern as bootstrap_done).
        ("is_deliverable",
         "ALTER TABLE goals ADD COLUMN is_deliverable INTEGER NOT NULL"
         " DEFAULT 0"),
        # anchor+claim (v14) — per-problem ingest sign-off pause flag. Additive
        # defaulted; sole writers are the Strategist `Ingest` commit (set) and
        # `asterism approve-ingest` / `reject-ingest` (clear). No version bump.
        ("ingest_signoff_pending",
         "ALTER TABLE problems ADD COLUMN ingest_signoff_pending INTEGER NOT"
         " NULL DEFAULT 0"),
    ):
        # entry_kind is load-bearing MID-CHAIN (the v18-era goals
        # rebuilds copy it by explicit column list) but dropped at v33 —
        # a DB already at/past v33 must never get it back.
        if col == "entry_kind" and v0 >= 33:
            continue
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    # Phase 2.5 — index on the freshly-added batch_id column. Lives
    # here (post-ALTER) rather than in SCHEMA because executescript
    # runs CREATE INDEX in declaration order, before the additive
    # ALTER block above ever runs — on pre-Phase 2.5 DBs that would
    # fail with "no such column: batch_id".
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sd_batch_id"
        " ON strategist_decisions(batch_id)"
    )
    # Backfill: mark every already-proved root as verified. Prior to
    # this column existing, `library.maybe_promote` (later
    # `verify.root_integrity_gate`) ran an axiom_probe on every proved
    # root every dispatcher tick — so any row currently sitting at
    # status='proved' has been kernel-axiom-validated under whatever
    # gate code was active at the time, just without a persistent
    # marker. The backfill turns that implicit history into explicit
    # DB state so the first post-migration dispatcher tick doesn't
    # re-pay ~30s × N proved roots (244 miniF2F + N stalls dispatch
    # ~110min on a benchmark-loaded workspace). Only meaningful on
    # the migration tick — on a fresh DB built from SCHEMA there are
    # no proved rows yet, so this is a no-op.
    conn.execute(
        "UPDATE goals SET integrity_verified = 1"
        " WHERE origin = 'root' AND status = 'proved'"
        "   AND integrity_verified = 0"
    )
    # Phase 7-D — drop the former cross-pipeline session_id columns.
    # The in-pipeline retry helper (Tooling/pipeline/_retry.py) keeps
    # sid as a local var for the pipeline's lifetime; the columns are
    # vestigial. Idempotent: a fresh DB built from the current SCHEMA
    # never had them, so DROP COLUMN raises "no such column" and we
    # swallow. Requires SQLite >= 3.35.0 (Python 3.12 ships ≥ 3.40).
    for col in ("builder_session_id", "backward_session_id"):
        try:
            conn.execute(f"ALTER TABLE goals DROP COLUMN {col}")
        except sqlite3.OperationalError as e:
            if "no such column" not in str(e).lower():
                raise
    conn.commit()

    # Phase 2 migration — CHECK-extension table-rebuild for
    # goals/pipelines/queue (SQLite cannot ALTER existing CHECK). Gated
    # by `PRAGMA user_version < 2`; fresh DBs (built directly from the
    # updated SCHEMA) skip the rebuild via the `'detached' in goals_cols`
    # detection. Idempotent.
    v = conn.execute("PRAGMA user_version").fetchone()[0]
    if v < 2:
        goals_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
        if 'detached' not in goals_cols:
            _migrate_to_phase2(conn)
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
    if v < 3:
        # Phase 2.5 — strategist_decisions.trigger_kind CHECK adds
        # 'inject_batch_done'. SQLite cannot extend CHECK in place;
        # rebuild required. Fresh DBs built from the updated SCHEMA
        # already have the widened CHECK + idx_sd_batch_id; the rebuild
        # short-circuits via the duplicate-index probe inside.
        _migrate_to_phase3(conn)
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
    if v < 4:
        # Phase 4 — goals.kind CHECK widens to accept 'def', 'structure',
        # 'class' (non-theorem toolkit kinds Forward can produce). Same
        # rebuild pattern as phase 3; idempotent via the in-DDL probe.
        _migrate_to_phase4(conn)
        conn.execute("PRAGMA user_version = 4")
        conn.commit()
    if v < 5:
        # Phase 5 — goals.status CHECK widens to accept 'frozen' (root
        # pre-launch state). Same rebuild pattern. Backfill: roots in
        # problems with bootstrap_done=0 flip to 'frozen' (matches the
        # legacy gate semantic — those roots were waiting for first_launch
        # anyway).
        _migrate_to_phase5(conn)
        conn.execute("PRAGMA user_version = 5")
        conn.commit()
    if v < 6:
        # Phase 6 — goals.status CHECK widens to accept 'dead' (terminal
        # for parent_needs_fix decline). Hard terminal like disproved
        # but doesn't block dedupe (same statement may be valid under a
        # different parent strategy). Same rebuild pattern as phase 5.
        # No backfill: pre-Phase-6 rows used 'shelved' for the
        # parent_needs_fix case; leaving them as 'shelved' is safe (just
        # means they're reopenable, which is harmless for already-completed
        # runs).
        _migrate_to_phase6(conn)
        conn.execute("PRAGMA user_version = 6")
        conn.commit()
    if v < 7:
        # Phase 7 — pipelines.kind + queue.kind CHECK widen to accept
        # 'Librarian' (the Library-ization pipeline). Same rebuild
        # pattern as earlier phases; idempotent via in-DDL CHECK probe.
        # No backfill: no pre-Phase-7 rows ever had kind='Librarian'.
        _migrate_to_phase7(conn)
        conn.execute("PRAGMA user_version = 7")
        conn.commit()
    if v < 8:
        # Phase 8 — library_decls.lifecycle CHECK widens to accept 'cleaned'
        # (Step 4 PR-ready state, after 'migrated'). Same rebuild pattern;
        # idempotent via the in-DDL CHECK probe. No backfill: pre-Phase-8
        # rows never had 'cleaned'.
        _migrate_to_phase8(conn)
        conn.execute("PRAGMA user_version = 8")
        conn.commit()
    if v < 9:
        # Phase 9 — library_decls gains `reopen_note` (the constraint a
        # downstream `needs-upstream` decline passes to a re-opened upstream's
        # re-cleanup). Plain ADD COLUMN (nullable) — no table rebuild. Guarded
        # so a fresh DB built from the updated SCHEMA (column already present)
        # doesn't double-add.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(library_decls)")}
        if "reopen_note" not in cols:
            conn.execute(
                "ALTER TABLE library_decls ADD COLUMN reopen_note TEXT")
        conn.execute("PRAGMA user_version = 9")
        conn.commit()
    if v < 10:
        # Phase 10 — library_decls gains `renamed_from` (the ORIGINAL fqn of a
        # P4-renamed kept decl; target_name holds the new fqn). Consumer files
        # read {renamed_from → target_name} as deferred-rewire renames. Plain
        # ADD COLUMN (nullable) — no table rebuild. Guarded so a fresh DB built
        # from the updated SCHEMA (column already present) doesn't double-add.
        cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(library_decls)")}
        if "renamed_from" not in cols:
            conn.execute(
                "ALTER TABLE library_decls ADD COLUMN renamed_from TEXT")
        conn.execute("PRAGMA user_version = 10")
        conn.commit()
    if v < 11:
        # Phase 11 — widen `strategies.status` CHECK to accept 'stalled'
        # (a parked-but-reopenable strategy whose subgoals all settled with
        # >=1 soft-shelved). Same rebuild pattern as phase 5/7/8. No
        # backfill: pre-Phase-11 rows in this state lingered as 'proposed';
        # the reconcile backstop migrates them to 'stalled' at runtime.
        _migrate_to_phase11(conn)
        conn.execute("PRAGMA user_version = 11")
        conn.commit()
    if v < 12:
        # Phase 12 — kb_entries drops `scope`. Breadth now reads off `node_id`
        # alone (NULL = problem-wide, set = node-bound); the scope enum was
        # 100% determined by node_id presence and its structural-depth model
        # was abandoned (lesson retrieval is semantic, not subtree-walk).
        # Idempotent: only drop when the column is still present (fresh DBs
        # built from the updated SCHEMA never had it). DROP COLUMN needs
        # SQLite >= 3.35.0 (Python 3.12 ships >= 3.40).
        kb_cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(kb_entries)")}
        if "scope" in kb_cols:
            conn.execute("ALTER TABLE kb_entries DROP COLUMN scope")
        conn.execute("PRAGMA user_version = 12")
        conn.commit()
    if v < 13:
        # Phase 13 — strategist_decisions.decision_kind CHECK widens to
        # accept 'MarkDeliverable' (anchor+claim architecture). SQLite
        # cannot ALTER a CHECK in place; rebuild required. Idempotent via
        # the in-DDL probe (fresh DBs built from the widened SCHEMA
        # short-circuit).
        _migrate_to_phase13(conn)
        conn.execute("PRAGMA user_version = 13")
        conn.commit()
    if v < 14:
        # Phase 14 — strategist_decisions.decision_kind CHECK widens again to
        # accept 'Ingest' (anchor+claim harvest trigger). Same table-rebuild
        # pattern as v13; idempotent via the in-DDL probe. (The additive
        # `problems.ingest_signoff_pending` column is handled by the ALTER
        # block above — no rebuild needed for it.)
        _migrate_to_phase14(conn)
        conn.execute("PRAGMA user_version = 14")
        conn.commit()
    if v < 15:
        # v15 — the additive-column COLLAPSE (task #10). Versions ≤14 grew a
        # second, UNVERSIONED migration channel: the blind-ALTER block above
        # (12 columns added over months with "no user_version bump needed"
        # notes), which made `user_version` an incomplete description of a
        # DB — two v14 DBs could differ by several columns depending on
        # which code revision last opened them (a live hazard for restores
        # from the .bak fleet and cross-revision reads). The ALTER block
        # runs earlier in THIS SAME init_schema pass, so stamping 15 here
        # certifies: v15 ⟹ the full additive set is present. POLICY from
        # v15 on: every new column ships as a versioned migration step —
        # the legacy ALTER block is FROZEN at 13 entries (ratchet-pinned by
        # test_db_phase7.py::test_additive_alter_block_is_frozen).
        conn.execute("PRAGMA user_version = 15")
        conn.commit()
    if v < 16:
        # v16 — Phase 6 (Root/Defs optional): `problems.ingested_at` is the
        # problem-level terminal state (Ingest = the only exit trigger).
        # Post-v15 discipline: a versioned step, NOT the frozen ALTER block.
        # Backfill: legacy problems whose root is proved+integrity_verified
        # are marked ingested ONCE so the new stall predicate ("Ingest not
        # yet emitted") does not re-trigger a Strategist on completed runs
        # (Phase 6 decision ②, 2026-07-04).
        cols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
        if "ingested_at" not in cols:
            conn.execute("ALTER TABLE problems ADD COLUMN ingested_at TEXT")
        conn.execute(
            "UPDATE problems SET ingested_at = ?"
            " WHERE ingested_at IS NULL AND name IN ("
            "   SELECT problem FROM goals WHERE origin = 'root'"
            "   AND status = 'proved' AND integrity_verified = 1)",
            (now(),),
        )
        conn.execute("PRAGMA user_version = 16")
        conn.commit()
    if v < 17:
        # v17 — queue contract upgrade (arch-review task #3): `problem`
        # (scope-safe recovery/pop — #74's structural fix), `payload` (JSON;
        # librarian per-file units stop smuggling `problem\x1ffile` through
        # target_id), `owner_pid`/`leased_at` (lease semantics — cross-
        # process in-flight visibility for concurrent dispatchers). The
        # queue is transient (cleared per-scope at startup, refill
        # re-derives), so no backfill: pre-v17 rows carry problem='' and
        # are swept by the next startup like any stale row.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(queue)")}
        for name, ddl in (
            ("problem", "ALTER TABLE queue ADD COLUMN problem TEXT NOT NULL"
                        " DEFAULT ''"),
            ("payload", "ALTER TABLE queue ADD COLUMN payload TEXT"),
            ("owner_pid", "ALTER TABLE queue ADD COLUMN owner_pid INTEGER"),
            ("leased_at", "ALTER TABLE queue ADD COLUMN leased_at TEXT"),
        ):
            if name not in cols:
                conn.execute(ddl)
        conn.execute("PRAGMA user_version = 17")
        conn.commit()
    if v < 18:
        # v18 — Library index moves into the DB (arch-review task #4, user
        # design call: SoT=DB, INDEX.md deleted).
        #   * library_decls.{signature, decl_kind}: kernel-true facts filled
        #     at bridge time from the declInfo oracle (NULL = not yet
        #     backfilled; consumers fall back to reading the .lean file).
        #   * problems.{library_bridged_at, library_bridge_note}: the chain's
        #     terminal done-marker (was: the `## <problem>` section existing
        #     in Library/INDEX.md — the ONE librarian checkpoint living
        #     outside the DB, string-matched four ways by consumers).
        # One-time backfill: parse the still-on-disk INDEX.md (workspace =
        # the DB file's parent) and mark its sections' problems bridged, so
        # already-harvested problems don't re-bridge after the cut-over.
        # :memory: / fresh DBs have no file and skip.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(library_decls)")}
        if "signature" not in cols:
            conn.execute("ALTER TABLE library_decls ADD COLUMN signature TEXT")
        if "decl_kind" not in cols:
            conn.execute("ALTER TABLE library_decls ADD COLUMN decl_kind TEXT")
        pcols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
        if "library_bridged_at" not in pcols:
            conn.execute(
                "ALTER TABLE problems ADD COLUMN library_bridged_at TEXT")
        if "library_bridge_note" not in pcols:
            conn.execute(
                "ALTER TABLE problems ADD COLUMN library_bridge_note TEXT")
        db_file = ""
        for _seq, _name, _file in conn.execute("PRAGMA database_list"):
            if _name == "main":
                db_file = _file or ""
        if db_file:
            legacy_index = Path(db_file).resolve().parent / "Library" / "INDEX.md"
            if legacy_index.is_file():
                try:
                    sections = [
                        ln[3:].strip()
                        for ln in legacy_index.read_text(
                            encoding="utf-8", errors="replace").splitlines()
                        if ln.startswith("## ")]
                except OSError:
                    sections = []
                for prob in sections:
                    conn.execute(
                        "UPDATE problems SET library_bridged_at = ?,"
                        " library_bridge_note = 'backfilled from legacy"
                        " INDEX.md (v18 migration)'"
                        " WHERE name = ? AND library_bridged_at IS NULL",
                        (now(), prob))
        conn.execute("PRAGMA user_version = 18")
        conn.commit()
    if v < 19:
        # v19 — goals.kind CHECK widens to accept 'inductive' (Forward may
        # mint new inductive types; the anchor+claim review carries the
        # trust surface — kernel anchorClosure already walks ctors). Same
        # rebuild pattern as phase 4; idempotent via the in-DDL probe.
        _migrate_to_v19(conn)
        conn.execute("PRAGMA user_version = 19")
        conn.commit()
    if v < 20:
        # v20 — goals.kind CHECK widens to accept 'instance' (named data
        # instances from Forward; anonymous rejected at parse). Same
        # live-column rebuild as v19, generalized.
        _widen_goals_kind_check(conn, ("theorem", "def", "structure",
                                       "class", "inductive", "instance"))
        conn.execute("PRAGMA user_version = 20")
        conn.commit()
    if v < 21:
        # v21 — spawn_usage: per-spawn token/turn accounting lands in the
        # DB (frontend charter §5-2). Historically the numbers lived only
        # in `[usage]` log lines + dead_attempts.artifacts (failed spawns
        # only), so successful spawns had no queryable spend and every
        # cost analysis was log archaeology.
        conn.execute(_SPAWN_USAGE_DDL)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spawn_usage_problem"
            " ON spawn_usage(problem, ts)")
        conn.execute("PRAGMA user_version = 21")
        conn.commit()
    if v < 22:
        # v22 — review snapshot (frontend charter §5-4): the anchor
        # closure needs a warm gateway (30s+ cold), so readers (serve
        # API GET, CLI default) must not compute it — the Ingest commit
        # stores it here while the gateway is warm; recompute is an
        # explicit act.
        pcols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
        if "review_snapshot" not in pcols:
            conn.execute(
                "ALTER TABLE problems ADD COLUMN review_snapshot TEXT")
        if "review_snapshot_at" not in pcols:
            conn.execute(
                "ALTER TABLE problems ADD COLUMN review_snapshot_at TEXT")
        conn.execute("PRAGMA user_version = 22")
        conn.commit()
    if v < 23:
        # v23 — paper pipeline v2 (D11): pipelines.kind + queue.kind
        # CHECK widen to 'Scholar'; strategist_decisions.decision_kind
        # widens to 'FetchPaper'. problem_papers itself needs no step
        # (CREATE TABLE IF NOT EXISTS in SCHEMA).
        _migrate_to_v23(conn)
        conn.execute("PRAGMA user_version = 23")
        conn.commit()
    if v < 24:
        # v24 — library_decls gains {docstring, src_line}: the remaining
        # declInfo-oracle facts the bridge already receives per file but
        # used to discard. The Library chapter's reading surface (serve)
        # becomes a DB read for doc + narrative order; its regex file
        # parse demotes to fallback for not-yet-backfilled rows.
        #   * docstring: '' = oracle confirmed the decl has no docstring;
        #     NULL = not yet backfilled (consumer falls back to file).
        #   * src_line: 1-based startLine of the decl's command range.
        # Backfill for already-bridged problems: one-shot
        # `asterism library-backfill-declinfo` (needs a warm gateway, so
        # not done here in-migration).
        cols = {r[1] for r in conn.execute("PRAGMA table_info(library_decls)")}
        if "docstring" not in cols:
            conn.execute("ALTER TABLE library_decls ADD COLUMN docstring TEXT")
        if "src_line" not in cols:
            conn.execute("ALTER TABLE library_decls ADD COLUMN src_line INTEGER")
        conn.execute("PRAGMA user_version = 24")
        conn.commit()
    if v < 25:
        # v25 — feature D: strategist_decisions.decision_kind widens to
        # 'AttemptDisproof' (Strategist suspects a user-requested claim
        # is FALSE → framework mechanically mints the ¬P goal; belief is
        # never trusted, both directions need the kernel).
        _migrate_to_v25(conn)
        conn.execute("PRAGMA user_version = 25")
        conn.commit()
    if v < 26:
        # v26 — strategist_decisions.trigger_kind widens to 'audit': the
        # wall-clock epistemic-auditor wake (default 180 min) that
        # re-derives plan-note claims against sources and curates the
        # note (b6 2026-07-11: a mis-annotated lever fossilized in the
        # note and walled the run; routine audits the TREE, nobody
        # audited the BELIEFS).
        _migrate_to_v26(conn)
        conn.execute("PRAGMA user_version = 26")
        conn.commit()
    if v < 27:
        # v27 — the ingest sign-off carries a signature: one JSON record
        # {name, at, snapshot_sha, evidence:{claude_email, os_user,
        # host}} written at approve. The name is the operator's claim;
        # the evidence is the machine's observation (captured, never
        # typed); snapshot_sha seals the exact reviewed content (v22
        # snapshot) — a later mismatch means the content changed after
        # it was signed. NULL = approved before signatures existed, or
        # signature revoked (reject / un-harvest).
        pcols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
        if "ingest_signoff" not in pcols:
            conn.execute(
                "ALTER TABLE problems ADD COLUMN ingest_signoff TEXT")
        conn.execute("PRAGMA user_version = 27")
        conn.commit()
    if v < 28:
        # v28 — `manifest_history` (shipped 12d6f6c, hours earlier)
        # generalizes to `user_file_history` (+file, +source columns):
        # the same first-load-baseline/change-record mechanism now
        # covers Root.lean and Defs.lean, and root_integrity_gate pins
        # a proved root to its baseline (self-audit §3-3). Existing
        # rows carry over as Manifest.md observations; the old table is
        # dropped (it lived <1 day, only baselines were recorded).
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "user_file_history" not in tables:
            conn.execute("""
                CREATE TABLE user_file_history (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem TEXT NOT NULL REFERENCES problems(name),
                    file    TEXT NOT NULL,
                    sha     TEXT NOT NULL,
                    body    TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    source  TEXT NOT NULL DEFAULT 'observed'
                            CHECK (source IN ('observed', 'repin'))
                )""")
        if "manifest_history" in tables:
            conn.execute(
                "INSERT INTO user_file_history"
                " (problem, file, sha, body, seen_at, source)"
                " SELECT problem, 'Manifest.md', sha, body, seen_at,"
                "        'observed'"
                " FROM manifest_history ORDER BY id")
            conn.execute("DROP TABLE manifest_history")
        conn.execute("PRAGMA user_version = 28")
        conn.commit()
    if v < 29:
        # v29 — problem FSM (problem_fsm_design.md §2): explicit
        # `problems.state`, backfilled from the legacy carriers
        # (ingested_at / ingest_signoff_pending / awaiting_human rows).
        # transitions.apply_problem_transition is the sole mutator.
        pcols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
        if "state" not in pcols:
            conn.execute(
                "ALTER TABLE problems ADD COLUMN state TEXT NOT NULL"
                " DEFAULT 'active' CHECK(state IN ('active',"
                " 'awaiting_human', 'ingest_signoff', 'ingested',"
                " 'revoked'))")
        conn.execute(
            "UPDATE problems SET state = CASE"
            " WHEN ingested_at IS NOT NULL AND ingest_signoff_pending = 1"
            "   THEN 'ingest_signoff'"
            " WHEN ingested_at IS NOT NULL THEN 'ingested'"
            " ELSE 'active' END")
        conn.execute(
            "UPDATE problems SET state = 'awaiting_human'"
            " WHERE state = 'active' AND name IN"
            " (SELECT DISTINCT problem FROM strategist_decisions"
            "  WHERE outcome = 'awaiting_human')")
        conn.execute("PRAGMA user_version = 29")
        conn.commit()
    if v < 30:
        # v30 — research mode (research_mode_design.md §2): the
        # Programme is the adversarially-reviewed argument layer
        # between the Manifest and the bricks. One row per RESOLVED
        # proposal cycle: `passed` rows form the revision chain (rev
        # strictly increasing per problem; the latest passed row is
        # the current Programme), `rejected` rows keep the discarded
        # proposal plus the full criticism dialogue for audit. SoT is
        # this table; PROGRAMME.md in the problem dir is a render.
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "programme_revisions" not in tables:
            conn.execute("""
                CREATE TABLE programme_revisions (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem    TEXT NOT NULL REFERENCES problems(name),
                    rev        INTEGER NOT NULL,
                    body       TEXT NOT NULL,
                    status     TEXT NOT NULL
                               CHECK (status IN ('passed', 'rejected')),
                    verdict    TEXT,
                    dialogue   TEXT,
                    rounds     INTEGER NOT NULL DEFAULT 0,
                    batch_id   TEXT,
                    created_at TEXT NOT NULL,
                    -- judge provenance (survey P1/P2, 2026-08-29);
                    -- old DBs get these via the post-ladder ALTER
                    judge_model    TEXT NULL DEFAULT NULL,
                    judge_provider TEXT NULL DEFAULT NULL,
                    judge_effort   TEXT NULL DEFAULT NULL,
                    rubric_sha     TEXT NULL DEFAULT NULL
                )""")
        conn.execute("PRAGMA user_version = 30")
        conn.commit()
    if v < 31:
        # v31 — pin the Programme chain invariant in the schema: at
        # most one PASSED row per (problem, rev). Single-daemon wake
        # serialization already guarantees it operationally; the
        # partial unique index makes a violation loud instead of a
        # silent forked chain (CLAUDE.md rule 6).
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_programme_passed_rev"
            " ON programme_revisions(problem, rev)"
            " WHERE status = 'passed'")
        conn.execute("PRAGMA user_version = 31")
        conn.commit()
    if v < 32:
        # v32 — batch attribution (#3, user call 2026-07-18):
        # `produced_kind` records HOW an Inject decision's artifact
        # came to be — 'minted' (fresh Forward decl), 'alias' (dedupe
        # landed it as an alias of an existing decl), 'reuse' (inject
        # repointed at an existing alive goal; nothing minted),
        # 'redispatch' (Backward/Builder re-fire at an existing goal),
        # 'disproof' (framework-minted ¬P goal). NULL = pre-v32 rows /
        # declines. The batch-outcomes render reads this instead of
        # guessing from joins (the success-without-landing /
        # nothing-attributed misattribution pair).
        pcols = {r[1] for r in conn.execute(
            "PRAGMA table_info(strategist_decisions)")}
        if "produced_kind" not in pcols:
            conn.execute(
                "ALTER TABLE strategist_decisions"
                " ADD COLUMN produced_kind TEXT NULL")
        conn.execute("PRAGMA user_version = 32")
        conn.commit()
    if v < 33:
        # v33 — Formalizer merge (update_plan_2026_07 #1):
        #   1. goals.entry_kind dropped — the merged worker decides
        #      prove-vs-split itself; pre-dispatch routing no longer
        #      exists (predecessor `difficulty` died the same death).
        #      Plain DROP COLUMN: SQLite ≥3.35 drops a column together
        #      with its column-level CHECK (verified on 3.42).
        #   2. queue + pipelines kind CHECK gains 'Formalizer'. Rebuild
        #      required (CHECKs are immutable in place). Old kind values
        #      stay VALID — historical rows are never rewritten.
        gcols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
        if "entry_kind" in gcols:
            conn.execute("ALTER TABLE goals DROP COLUMN entry_kind")
        # Per-table guards, and MISSING table fails LOUD (a prior v33
        # attempt that crashed between DROP and RENAME must not be
        # papered over by a skip that then stamps v33 — review 07-27 #3).
        rebuilds = {
            "pipelines": """
                CREATE TABLE _new_pipelines (
                    id          TEXT PRIMARY KEY,
                    kind        TEXT NOT NULL
                                    CHECK(kind IN ('Builder','Backward',
                                                   'Verify','Strategist',
                                                   'Forward','Librarian',
                                                   'Scholar','Formalizer')),
                    target_id   TEXT NOT NULL,
                    target_kind TEXT NOT NULL
                                    CHECK(target_kind IN
                                          ('Goal','Strategy','Problem')),
                    status      TEXT NOT NULL
                                    CHECK(status IN ('succeeded','failed')),
                    outcome     TEXT NOT NULL,
                    started_at  TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );
                INSERT INTO _new_pipelines SELECT * FROM pipelines;
                DROP TABLE pipelines;
                ALTER TABLE _new_pipelines RENAME TO pipelines;
                CREATE INDEX IF NOT EXISTS idx_pipelines_status
                    ON pipelines(status);
            """,
            "queue": """
                CREATE TABLE _new_queue (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind        TEXT NOT NULL
                                    CHECK(kind IN ('Builder','Backward',
                                                   'Verify','Strategist',
                                                   'Forward','Librarian',
                                                   'Scholar','Formalizer')),
                    target_id   TEXT NOT NULL,
                    target_kind TEXT NOT NULL DEFAULT 'Goal'
                                    CHECK(target_kind IN
                                          ('Goal','Strategy','Problem')),
                    priority    INTEGER NOT NULL DEFAULT 0,
                    decision_id INTEGER NULL DEFAULT NULL
                                    REFERENCES strategist_decisions(id),
                    problem     TEXT NOT NULL DEFAULT '',
                    payload     TEXT,
                    owner_pid   INTEGER,
                    leased_at   TEXT,
                    created_at  TEXT NOT NULL
                );
                INSERT INTO _new_queue (id, kind, target_id, target_kind,
                    priority, decision_id, problem, payload, owner_pid,
                    leased_at, created_at)
                SELECT id, kind, target_id, target_kind, priority,
                    decision_id, problem, payload, owner_pid,
                    leased_at, created_at FROM queue;
                DROP TABLE queue;
                ALTER TABLE _new_queue RENAME TO queue;
                CREATE INDEX IF NOT EXISTS idx_queue_priority
                    ON queue(priority DESC, id ASC);
            """,
        }
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            for tbl, script in rebuilds.items():
                row = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table'"
                    " AND name=?", (tbl,)).fetchone()
                if row is None:
                    raise RuntimeError(
                        f"v33: table {tbl!r} missing — a prior migration "
                        f"attempt crashed mid-rebuild; restore the DB "
                        f"from backup before retrying")
                if "'Formalizer'" in (row[0] or ""):
                    continue  # this table already rebuilt (idempotent)
                conn.executescript(script)
            fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
            if fk_violations:
                raise RuntimeError(
                    f"v33 migration left FK violations: "
                    f"{fk_violations[:5]}")
        finally:
            conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA user_version = 33")
        conn.commit()
    if v < 34:
        # v34 — why a proposal was discarded. Pre-v34 only the
        # Adversary-exhaustion path recorded a `rejected` row; the
        # mechanical paths (verify rounds exhausted, revision spawn
        # rc≠0) discarded the batch with no record anywhere, so the
        # next wake inherited a plan note describing a dispatch that
        # never happened and no reason it didn't (07-29 SG: two wakes
        # burned reconstructing it). Additive nullable; NULL on
        # pre-v34 rows = the legacy Adversary-rejection wording.
        rcols = {r[1] for r in conn.execute(
            "PRAGMA table_info(programme_revisions)")}
        if "discard_reason" not in rcols:
            conn.execute(
                "ALTER TABLE programme_revisions"
                " ADD COLUMN discard_reason TEXT NULL")
        conn.execute("PRAGMA user_version = 34")
        conn.commit()
    if v < 35:
        # v35 — the discussion group tree (discussion_group_design.md).
        # Schema only: this step introduces the `groups` table and the
        # columns that point at it, backfills one TOP group per problem
        # (every pre-v35 row belongs to it), and widens the three CHECK
        # constraints the new decision kinds and the per-group wake seat
        # need. No behaviour changes here — the readers still run through
        # the top group exactly as before.
        _migrate_to_v35(conn)
        conn.execute("PRAGMA user_version = 35")
        conn.commit()
    if v < 36:
        # v36 — `goal_events`: every goal status transition, append-only.
        # Purely additive (new table + two indexes); no existing row is
        # touched and no reader depends on it yet, so an old DB opened
        # after this simply starts recording from now on. History is NOT
        # backfilled — `goals.updated_at` is not an event clock (attempts,
        # is_deliverable and integrity_verified all bump it), and a
        # fabricated past is worse in a forensics table than an honest
        # start line.
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS goal_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id     INTEGER NOT NULL
                            REFERENCES goals(id) ON DELETE CASCADE,
            problem     TEXT NOT NULL REFERENCES problems(name),
            from_status TEXT NULL DEFAULT NULL,
            to_status   TEXT NOT NULL,
            event       TEXT NOT NULL DEFAULT '',
            reason      TEXT NOT NULL DEFAULT '',
            at          TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_goal_events_goal
            ON goal_events(goal_id, at);
        CREATE INDEX IF NOT EXISTS idx_goal_events_problem
            ON goal_events(problem, at);
        """)
        conn.execute("PRAGMA user_version = 36")
        conn.commit()
    if v < 37:
        # v37 — `programme_revisions.discard_channel`: WHICH channel
        # dropped a proposal, as a machine-readable value (the registry
        # failure_reason verbatim), not prose. `discard_reason` is free
        # text an agent's next wake must not be routed on — gates read
        # structured signals (CLAUDE.md), and this one decides whether
        # the successor sees the rejected draft (infra death: nobody
        # refuted the argument) or only the one-line notice (adversary
        # exhaustion: the ratified anti-anchoring semantics of
        # research_mode_design §1/§3). Additive nullable; NULL on older
        # rows reads as the adversarial channel, which is what every
        # pre-v34 row actually was.
        rcols = {r[1] for r in conn.execute(
            "PRAGMA table_info(programme_revisions)")}
        if "discard_channel" not in rcols:
            conn.execute(
                "ALTER TABLE programme_revisions"
                " ADD COLUMN discard_channel TEXT NULL")
        conn.execute("PRAGMA user_version = 37")
        conn.commit()
    if v < 38:
        # v38 — pipeline rows exist for the whole pipeline LIFETIME:
        # INSERTed status='running' at dispatch, UPDATEd at completion.
        # Widens the status CHECK with 'running' and relaxes outcome /
        # finished_at to NULL (a running row has neither). Motive: with
        # the FK target present from dispatch, `dead_attempts` rows are
        # written eagerly, 1:1 with each goals.attempts increment — the
        # pre-v38 buffer-until-normal-return protocol lost the forensic
        # rows whenever the worker thread died by exception while the
        # eager increments stayed banked (goal 7486, 2026-08-08:
        # attempts=10 vs 7 dead_attempts rows; the drift distorted
        # dispatch.shelve_threshold input and misled an operator audit).
        _migrate_to_v38(conn)
        conn.execute("PRAGMA user_version = 38")
        conn.commit()
    if v < 39:
        # v39 — `groups.conventions_seed`: the parent's `## Conventions`
        # snapshotted when the group was opened. Conventions stopped
        # walking the ancestor chain (a sub-group's workers were reading
        # two sibling research lines' working notes, 3,088 B of graph
        # vocabulary for a brick with no graph in it), so a child that
        # never inherits also never LEARNS a parent's footgun — and it
        # cannot ask for a rule it does not know exists. The seed is that
        # one-time hand-off; it is read only until the group ships its own
        # section. Additive with a default: pre-v39 groups seed empty,
        # which is what they have been running on all along.
        gcols = {r[1] for r in conn.execute("PRAGMA table_info(groups)")}
        if "conventions_seed" not in gcols:
            conn.execute(
                "ALTER TABLE groups"
                " ADD COLUMN conventions_seed TEXT NOT NULL DEFAULT ''")
        conn.execute("PRAGMA user_version = 39")
        conn.commit()
    if v < 40:
        # v40 — the Manifest.md retirement (owner surgery 2026-08-19).
        # A problem's user intent moves fully into the DB: the GOAL is
        # the top group's `groups.charter` (the old equation
        # `charter : sub-group :: Manifest : problem` becomes literal),
        # the user's WORD (standing directives) is `problems.user_word`,
        # and machine settings live in `problem_settings` alone (the
        # 2026-07-07 frontmatter dissolve loses its file fallback).
        # Backfill for a pre-v40 DB, in order:
        #   1. add `problems.user_word` (empty — the retired body was
        #      never split; it lands whole in the charter);
        #   2. for every problem, read the still-on-disk Manifest.md via
        #      the doomed `manifest_path` column: copy its body into the
        #      top group's charter (only where that charter is still
        #      empty), seed absent `problem_settings` keys from the
        #      frontmatter (else the axiom gates would silently weaken
        #      to defaults when the file fallback disappears), and
        #      record the charter baseline in `user_file_history`.
        #      Best-effort: a missing/garbled file leaves the charter
        #      empty for the doctor to flag.
        #   3. DROP `problems.manifest_path`.
        # The parsing here is a frozen copy of the retired parser —
        # migration code is amber; the live module is gone.
        _migrate_to_v40(conn)
        conn.execute("PRAGMA user_version = 40")
        conn.commit()
    if v < 41:
        # v41 — retire stranded Manifest.md amend requests (owner call
        # 2026-08-19). A pre-v40 `RequestUserAmend` row with payload
        # file='Manifest.md' that was still awaiting_human can no
        # longer be resolved: `amend._ALLOWED_FILES` is now
        # (Defs.lean, Root.lean, charter), and `resolve_amend` hits
        # that whitelist BEFORE both the accept and reject paths — so
        # the Inbox card could neither be applied nor dismissed and
        # its problem stayed paused forever (one such row in the live
        # DB: id 213, Topology.brouwer_fixed_point, awaiting since
        # 2026-05-22 — ruled moot rather than re-targeted). Historical
        # resolved rows keep their payloads untouched; only stranded
        # awaiting_human rows are auto-rejected, and their problems'
        # awaiting_human pause lifts when no other request holds it.
        _migrate_to_v41(conn)
        conn.execute("PRAGMA user_version = 41")
        conn.commit()
    if v < 42:
        # v42 — problem_papers.origin becomes the calling seat (owner
        # ruling 2026-08-22: paper_fetch is any seat's tool now, the
        # Scholar pipeline retired). The old CHECK allowed only
        # manifest/scholar/user, and bind_paper's INSERT OR IGNORE
        # swallowed the CHECK violation SILENTLY — a strategist's
        # direct fetch shelved the paper and bound nothing. SQLite
        # cannot widen a CHECK in place; rebuild the table.
        _migrate_to_v42(conn)
        conn.execute("PRAGMA user_version = 42")
        conn.commit()
    if v < 43:
        # v43 — strategist_decisions.trigger_kind gains 'stall' (owner
        # ruling 2026-08-24, reversing the deliberate 2026-07-04
        # conflation with inject_batch_done): every T4 structural-stall
        # rescue may mark an upstream anomaly, and the conflation made
        # the rate invisible to SQL — the '[stall-wake]' log line was
        # the only record. SQLite cannot widen a CHECK in place;
        # rebuild from the LIVE table's own DDL (sqlite_master), so the
        # migration cannot drift from whatever column vintage the
        # on-disk table carries.
        _migrate_to_v43(conn)
        conn.execute("PRAGMA user_version = 43")
        conn.commit()
    if v < 44:
        # v44 — strategy_subgoals.link_kind: 'minted' (the strategy
        # created this sub-goal — authorship) vs 'cited' (it reuses a
        # pre-existing sibling — dependency/wait edge). The brief-
        # inheritance walk treated every edge as authorship and leaked
        # a redispatch brief sideways into a cited sibling's whole
        # subtree (2026-08-25: six intake mis-aimed declines in three
        # minutes on union_closed). Additive column; backfill below.
        _migrate_to_v44(conn)
        conn.execute("PRAGMA user_version = 44")
        conn.commit()
    if v < 45:
        # v45 — the routine wake is an audit (owner design 2026-08-30):
        # strategist_decisions.trigger_kind gains 'routine_fired' (the
        # action wake a fired audit seats); the routine_verdicts table
        # itself arrives via the SCHEMA's CREATE TABLE IF NOT EXISTS.
        # SQLite cannot widen a CHECK in place; rebuild from the live
        # DDL as v43 did.
        _migrate_to_v45(conn)
        conn.execute("PRAGMA user_version = 45")
        conn.commit()

    # Judge provenance columns (calibration survey P1/P2, 2026-08-29).
    # Additive nullable audit columns, no version bump (the
    # last_routine_at pattern) — but they live AFTER the ladder, not in
    # the top additive loop: programme_revisions is only born at v30,
    # and the loop's except tolerates duplicate columns, not missing
    # tables. Guarded by table_info, so fresh DBs (whose v30 CREATE
    # already carries them) no-op here.
    pr_cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(programme_revisions)")}
    for col in ("judge_model", "judge_provider", "judge_effort",
                "rubric_sha"):
        if col not in pr_cols:
            conn.execute(f"ALTER TABLE programme_revisions"
                         f" ADD COLUMN {col} TEXT NULL DEFAULT NULL")
    conn.commit()


def _migrate_to_v41(conn: sqlite3.Connection) -> None:
    from .db import now as _now
    import json as _json
    stranded = []
    for row in conn.execute(
            "SELECT id, problem, payload FROM strategist_decisions"
            " WHERE decision_kind = 'RequestUserAmend'"
            "   AND outcome = 'awaiting_human'").fetchall():
        try:
            file = str(_json.loads(row[2] or "{}").get("file", ""))
        except (TypeError, ValueError):
            continue
        if file == "Manifest.md":
            stranded.append((int(row[0]), str(row[1])))
    for rid, problem in stranded:
        conn.execute(
            "UPDATE strategist_decisions SET outcome = 'rejected',"
            " outcome_detail = 'auto-rejected at v41: the Manifest.md"
            " amend target retired with v40; the request predates the"
            " retirement and was ruled moot', updated_at = ?"
            " WHERE id = ?", (_now(), rid))
        # Lift the pause only when nothing else holds it (mirrors
        # resolve_amend's gate-lift; direct state write is the
        # migration precedent, cf. the v29 backfill).
        still = conn.execute(
            "SELECT 1 FROM strategist_decisions WHERE problem = ?"
            "   AND outcome = 'awaiting_human' LIMIT 1",
            (problem,)).fetchone()
        if still is None:
            conn.execute(
                "UPDATE problems SET state = 'active'"
                " WHERE name = ? AND state = 'awaiting_human'",
                (problem,))
        print(f"[v41] {problem}: stranded Manifest.md amend row {rid}"
              f" auto-rejected", flush=True)


def _v40_parse_legacy_manifest(text: str) -> "tuple[dict, str]":
    """(frontmatter dict, body) — frozen minimal copy of the retired
    Manifest.md parser (state/manifest.py, deleted at v40). Inline and
    block YAML lists, plain scalars; body = everything after the
    frontmatter block, stripped."""
    import re as _re
    fm_re = _re.compile(r"^---\n(.*?)\n---\n", _re.DOTALL)
    m = fm_re.match(text)
    fm: dict = {}
    if m:
        current_list_key = None
        for line in m.group(1).splitlines():
            if not line.strip():
                current_list_key = None
                continue
            if line.startswith('  - ') or line.startswith('- '):
                if current_list_key:
                    fm.setdefault(current_list_key, []).append(
                        line.lstrip(' -').strip().strip("'\""))
                continue
            if ':' in line and not line.startswith(' '):
                key, _, val = line.partition(':')
                key, val = key.strip(), val.strip()
                if val == '':
                    current_list_key = key
                    fm[key] = []
                elif val.startswith('['):
                    inner = val.strip('[]').strip()
                    fm[key] = [s.strip().strip("'\"")
                               for s in inner.split(',') if s.strip()]
                    current_list_key = None
                else:
                    fm[key] = val.strip("'\"")
                    current_list_key = None
    body = (text[m.end():] if m else text).strip()
    return fm, body


def _migrate_to_v40(conn: sqlite3.Connection) -> None:
    from .db import now as _now
    import hashlib as _hashlib
    import json as _json

    pcols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
    if "user_word" not in pcols:
        conn.execute(
            "ALTER TABLE problems ADD COLUMN user_word TEXT NOT NULL"
            " DEFAULT ''")
    if "manifest_path" not in pcols:
        return  # fresh DB built from the v40 SCHEMA — nothing to migrate

    # Workspace = the DB file's parent (v18 precedent); :memory: skips.
    db_file = ""
    for _seq, _name, _file in conn.execute("PRAGMA database_list"):
        if _name == "main":
            db_file = _file or ""
    ws = Path(db_file).resolve().parent if db_file else None

    for row in conn.execute(
            "SELECT name, manifest_path FROM problems").fetchall():
        problem, rel = str(row[0]), str(row[1] or "")
        if ws is None or not rel:
            continue
        path = ws / rel
        try:
            fm, body = _v40_parse_legacy_manifest(
                path.read_text(encoding="utf-8"))
        except OSError:
            # Manifest.md already gone — the corpus conversion may have
            # replaced it with problem.json before this DB was next
            # opened (the 2026-08-19 cut-over ran exactly that way).
            # Seed from the converted file; only when BOTH are missing
            # does the charter stay empty for the doctor to flag.
            try:
                seed = _json.loads((path.parent / "problem.json")
                                   .read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            body = str(seed.get("charter", "")).strip()
            fm = dict(seed.get("settings") or {})
        if body:
            top = conn.execute(
                "SELECT id, charter FROM groups WHERE problem = ?"
                " AND parent_group_id IS NULL", (problem,)).fetchone()
            if top is not None and not str(top[1] or "").strip():
                conn.execute(
                    "UPDATE groups SET charter = ?, updated_at = ?"
                    " WHERE id = ?", (body, _now(), int(top[0])))
                conn.execute(
                    "INSERT INTO user_file_history"
                    " (problem, file, sha, body, seen_at, source)"
                    " VALUES (?, 'charter', ?, ?, ?, 'observed')",
                    (problem,
                     _hashlib.sha256(
                         body.encode("utf-8")).hexdigest()[:16],
                     body, _now()))
        # Settings: seed only ABSENT keys — a later UI edit is never
        # clobbered by a stale file (same contract migrate_from_manifest
        # kept during the dual-read window).
        present = {str(r[0]) for r in conn.execute(
            "SELECT key FROM problem_settings WHERE problem = ?",
            (problem,))}
        seed: dict = {}
        for key in ("axioms_whitelist", "forbidden_lemmas"):
            val = fm.get(key)
            if isinstance(val, list):
                seed[key] = [str(x) for x in val]
        if "library" in fm:
            seed["library"] = str(fm["library"]).strip().lower() in (
                "true", "yes", "1")
        if "signoff" in fm:
            seed["signoff"] = str(fm["signoff"]).strip().lower() not in (
                "false", "no", "0")
        for key, val in seed.items():
            if key in present:
                continue
            conn.execute(
                "INSERT INTO problem_settings"
                " (problem, key, value, updated_at) VALUES (?, ?, ?, ?)",
                (problem, key, _json.dumps(val), _now()))

    conn.execute("ALTER TABLE problems DROP COLUMN manifest_path")


def _migrate_to_v35(conn: sqlite3.Connection) -> None:
    """v35 — discussion groups: new table, pointers, CHECK widenings.

    Three CHECKs have to widen, and SQLite cannot alter a CHECK in
    place, so each is a point-in-time rebuild-and-copy guarded by a
    substring probe on the stored DDL (the v33 pattern):

      * `strategist_decisions.decision_kind` — 'Delegate' /
        'ReturnToParent'. The rebuild also adds `group_id` (which group
        authored the decision) and `produced_group_id` (the group a
        Delegate opened — the third form of produced work).
      * `queue.target_kind` / `pipelines.target_kind` — 'Group', so a
        Strategist seat can belong to one group instead of the whole
        problem.

    Backfill: one top group per problem (`parent_group_id IS NULL`),
    carrying the problem's existing wake clocks, and every existing
    programme revision / decision row pointed at it. After this step a
    pre-v35 DB describes exactly the same tree it did before — as a
    one-group tree.
    """
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}

    # 1 — the table itself (fresh DBs already have it from SCHEMA).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            problem         TEXT NOT NULL REFERENCES problems(name),
            parent_group_id INTEGER NULL DEFAULT NULL
                                REFERENCES groups(id) ON DELETE CASCADE,
            charter         TEXT NOT NULL DEFAULT '',
            anchor_goal_id  INTEGER NULL DEFAULT NULL
                                REFERENCES goals(id) ON DELETE SET NULL,
            opened_by       INTEGER NULL DEFAULT NULL
                                REFERENCES strategist_decisions(id)
                                ON DELETE SET NULL,
            status          TEXT NOT NULL DEFAULT 'active'
                                CHECK(status IN ('active', 'delivered',
                                                 'returned', 'closed')),
            last_routine_at    TEXT NULL DEFAULT NULL,
            last_strategist_at TEXT NULL DEFAULT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )""")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_groups_top ON groups(problem)"
        " WHERE parent_group_id IS NULL")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_groups_problem ON groups(problem)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_groups_parent"
        " ON groups(parent_group_id)")

    # 2 — programme_revisions.group_id (additive; the table is created by
    #     the v30 step, so it exists by now on every DB that has one).
    if "programme_revisions" in tables:
        rcols = {r[1] for r in conn.execute(
            "PRAGMA table_info(programme_revisions)")}
        if "group_id" not in rcols:
            conn.execute(
                "ALTER TABLE programme_revisions"
                " ADD COLUMN group_id INTEGER NULL REFERENCES groups(id)")

    # 3 — the three CHECK widenings.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        _v35_rebuild_strategist_decisions(conn)
        _v35_rebuild_target_kind(conn, "queue")
        _v35_rebuild_target_kind(conn, "pipelines")
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"v35 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")

    # 4 — one top group per problem, carrying the problem's wake clocks.
    ts = now()
    for row in conn.execute("SELECT name FROM problems").fetchall():
        problem = str(row[0])
        if conn.execute(
            "SELECT 1 FROM groups WHERE problem = ?"
            " AND parent_group_id IS NULL", (problem,)
        ).fetchone() is not None:
            continue
        clocks = conn.execute(
            "SELECT last_routine_at, last_strategist_at FROM problems"
            " WHERE name = ?", (problem,)).fetchone()
        conn.execute(
            "INSERT INTO groups (problem, parent_group_id, charter,"
            " status, last_routine_at, last_strategist_at,"
            " created_at, updated_at)"
            " VALUES (?, NULL, '', 'active', ?, ?, ?, ?)",
            (problem, clocks[0] if clocks else None,
             clocks[1] if clocks else None, ts, ts))

    # 5 — point every pre-v35 row at its problem's top group.
    top_sql = ("(SELECT g.id FROM groups g WHERE g.problem = %s.problem"
               "   AND g.parent_group_id IS NULL)")
    conn.execute(
        "UPDATE strategist_decisions SET group_id = "
        + (top_sql % "strategist_decisions") + " WHERE group_id IS NULL")
    if "programme_revisions" in tables:
        conn.execute(
            "UPDATE programme_revisions SET group_id = "
            + (top_sql % "programme_revisions") + " WHERE group_id IS NULL")
        # The chain-uniqueness invariant (v31) moves from the problem to
        # the group: each group owns its own rev numbering from 1.
        conn.execute("DROP INDEX IF EXISTS ux_programme_passed_rev")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_programme_passed_rev"
            " ON programme_revisions(group_id, rev) WHERE status = 'passed'")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sd_group"
        " ON strategist_decisions(group_id)")


def _v35_rebuild_strategist_decisions(conn: sqlite3.Connection) -> None:
    """Widen `decision_kind` and add the two group pointers."""
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='strategist_decisions'").fetchone()
    if chk is None:
        raise RuntimeError(
            "v35: strategist_decisions is missing — a prior migration "
            "crashed mid-rebuild; restore the DB from backup")
    if "'Delegate'" in (chk[0] or ""):
        return  # already rebuilt (idempotent)
    # `produced_kind` arrived as a v32 ALTER, so it is not in any earlier
    # CREATE statement — carry it explicitly or the copy drops it.
    conn.executescript("""
        CREATE TABLE _new_strategist_decisions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            problem             TEXT NOT NULL REFERENCES problems(name),
            triggered_at_tick   INTEGER NOT NULL,
            trigger_kind        TEXT NOT NULL
                                    CHECK(trigger_kind IN
                                          ('first_launch','pending_review',
                                           'routine','inject_batch_done',
                                           'audit')),
            decision_kind       TEXT NOT NULL
                                    CHECK(decision_kind IN
                                          ('Inject','ConfirmShelve','Reopen',
                                           'EmitDirective','InitializeDefs',
                                           'RequestUserAmend','Noop',
                                           'MarkDeliverable','Ingest',
                                           'FetchPaper','AttemptDisproof',
                                           'Delegate','ReturnToParent',
                                           'CloseGroup')),
            group_id            INTEGER NULL DEFAULT NULL
                                    REFERENCES groups(id) ON DELETE SET NULL,
            target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
            brief               TEXT NULL DEFAULT NULL,
            reason              TEXT NULL DEFAULT NULL,
            payload             TEXT NOT NULL DEFAULT '{}',
            batch_id            TEXT NULL DEFAULT NULL,
            produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                                    ON DELETE SET NULL,
            produced_strategy_id INTEGER NULL DEFAULT NULL
                                    REFERENCES strategies(id) ON DELETE SET NULL,
            produced_group_id   INTEGER NULL DEFAULT NULL
                                    REFERENCES groups(id) ON DELETE SET NULL,
            outcome             TEXT NULL DEFAULT NULL,
            outcome_detail      TEXT NULL DEFAULT NULL,
            produced_kind       TEXT NULL DEFAULT NULL,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL
        );
        INSERT INTO _new_strategist_decisions
            (id, problem, triggered_at_tick, trigger_kind, decision_kind,
             target_id, brief, reason, payload, batch_id, produced_goal_id,
             produced_strategy_id, outcome, outcome_detail, produced_kind,
             created_at, updated_at)
        SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
               target_id, brief, reason, payload, batch_id, produced_goal_id,
               produced_strategy_id, outcome, outcome_detail, produced_kind,
               created_at, updated_at
        FROM strategist_decisions;
        DROP TABLE strategist_decisions;
        ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
        CREATE INDEX IF NOT EXISTS idx_sd_problem
            ON strategist_decisions(problem);
        CREATE INDEX IF NOT EXISTS idx_sd_outcome
            ON strategist_decisions(outcome);
        CREATE INDEX IF NOT EXISTS idx_sd_batch_id
            ON strategist_decisions(batch_id);
    """)


#: `queue` and `pipelines` differ only in the columns around the CHECK, so
#: the widening is a textual one: take the stored DDL and add 'Group' to
#: the target_kind enum. Rebuilding from a hand-copied schema would have to
#: be kept in sync with two tables that other migrations also touch.
_V35_TARGET_KIND_OLD = "('Goal','Strategy','Problem')"
_V35_TARGET_KIND_NEW = "('Goal','Strategy','Problem','Group')"


def _v35_rebuild_target_kind(conn: sqlite3.Connection, table: str) -> None:
    """Add 'Group' to `table`.target_kind's CHECK, preserving every row."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
        (table,)).fetchone()
    if row is None:
        raise RuntimeError(
            f"v35: {table} is missing — a prior migration crashed "
            f"mid-rebuild; restore the DB from backup")
    ddl = row[0] or ""
    if "'Group'" in ddl:
        return  # already widened (idempotent)
    if _V35_TARGET_KIND_OLD not in ddl:
        raise RuntimeError(
            f"v35: cannot widen {table}.target_kind — the stored CHECK "
            f"does not contain {_V35_TARGET_KIND_OLD}; schema drifted, "
            f"widen it by hand rather than guessing")
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    collist = ", ".join(cols)
    indexes = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name = ?"
        " AND sql IS NOT NULL", (table,)).fetchall()]
    new_ddl = ddl.replace(_V35_TARGET_KIND_OLD, _V35_TARGET_KIND_NEW, 1)
    # `CREATE TABLE [IF NOT EXISTS] "name"` → the temp name, first hit only.
    new_ddl = new_ddl.replace(table, f"_new_{table}", 1)
    conn.executescript(
        f"{new_ddl};\n"
        f"INSERT INTO _new_{table} ({collist})"
        f" SELECT {collist} FROM {table};\n"
        f"DROP TABLE {table};\n"
        f"ALTER TABLE _new_{table} RENAME TO {table};\n")
    for idx_sql in indexes:
        conn.execute(idx_sql)


def _migrate_to_v38(conn: sqlite3.Connection) -> None:
    """v38 — rebuild `pipelines` so status admits 'running' and
    outcome / finished_at admit NULL (SQLite cannot alter a CHECK or a
    NOT NULL in place). Point-in-time rebuild-and-copy, idempotent via a
    substring probe on the stored DDL (the v33/v35 pattern). The column
    set is fixed by v35 (every DB at v37 has passed the v33 kind-widen
    and the v35 target_kind-widen), so the new DDL is written out in
    full — it must stay token-identical to the SCHEMA block in db.py
    (test_pipelines_v38 compares fresh vs migrated table_info)."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='pipelines'").fetchone()
    if row is None:
        raise RuntimeError(
            "v38: pipelines is missing — a prior migration crashed "
            "mid-rebuild; restore the DB from backup")
    if "'running'" in (row[0] or ""):
        return  # already rebuilt (idempotent)
    indexes = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index'"
        " AND tbl_name='pipelines' AND sql IS NOT NULL").fetchall()]
    # dead_attempts.pipeline_id FKs this table: rebuild under
    # foreign_keys=OFF and assert no violations after (v35 pattern).
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_pipelines (
                id          TEXT PRIMARY KEY,
                kind        TEXT NOT NULL
                                CHECK(kind IN ('Builder','Backward','Verify',
                                               'Strategist','Forward',
                                               'Librarian','Scholar',
                                               'Formalizer')),
                target_id   TEXT NOT NULL,
                target_kind TEXT NOT NULL
                                CHECK(target_kind IN ('Goal','Strategy',
                                                      'Problem','Group')),
                status      TEXT NOT NULL CHECK(status IN ('running',
                                                           'succeeded',
                                                           'failed')),
                outcome     TEXT NULL,
                started_at  TEXT NOT NULL,
                finished_at TEXT NULL
            );
            INSERT INTO _new_pipelines
                (id, kind, target_id, target_kind, status, outcome,
                 started_at, finished_at)
            SELECT id, kind, target_id, target_kind, status, outcome,
                   started_at, finished_at
            FROM pipelines;
            DROP TABLE pipelines;
            ALTER TABLE _new_pipelines RENAME TO pipelines;
        """)
        for idx_sql in indexes:
            conn.execute(idx_sql)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"v38 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_v26(conn: sqlite3.Connection) -> None:
    """v26 — widen strategist_decisions.trigger_kind to also accept
    'audit'. Same point-in-time rebuild-and-copy as v25 (columns
    unchanged since v22; only the two CHECK clauses evolve)."""
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='strategist_decisions'").fetchone()
    if chk and "'audit'" in (chk["sql"] or ""):
        return  # fresh DB from SCHEMA, or re-run

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategist_decisions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                problem             TEXT NOT NULL REFERENCES problems(name),
                triggered_at_tick   INTEGER NOT NULL,
                trigger_kind        TEXT NOT NULL
                                        CHECK(trigger_kind IN
                                              ('first_launch','pending_review',
                                               'routine','inject_batch_done',
                                               'audit')),
                decision_kind       TEXT NOT NULL
                                        CHECK(decision_kind IN
                                              ('Inject','ConfirmShelve','Reopen',
                                               'EmitDirective','InitializeDefs',
                                               'RequestUserAmend','Noop',
                                               'MarkDeliverable','Ingest',
                                               'FetchPaper','AttemptDisproof')),
                target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                brief               TEXT NULL DEFAULT NULL,
                reason              TEXT NULL DEFAULT NULL,
                payload             TEXT NOT NULL DEFAULT '{}',
                batch_id            TEXT NULL DEFAULT NULL,
                produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                                        ON DELETE SET NULL,
                produced_strategy_id INTEGER NULL DEFAULT NULL
                                        REFERENCES strategies(id) ON DELETE SET NULL,
                outcome             TEXT NULL DEFAULT NULL,
                outcome_detail      TEXT NULL DEFAULT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
            INSERT INTO _new_strategist_decisions
                (id, problem, triggered_at_tick, trigger_kind, decision_kind,
                 target_id, brief, reason, payload, batch_id, produced_goal_id,
                 produced_strategy_id, outcome, outcome_detail,
                 created_at, updated_at)
            SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
                   target_id, brief, reason, payload, batch_id, produced_goal_id,
                   produced_strategy_id, outcome, outcome_detail,
                   created_at, updated_at
            FROM strategist_decisions;
            DROP TABLE strategist_decisions;
            ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
            CREATE INDEX IF NOT EXISTS idx_sd_problem
                ON strategist_decisions(problem);
            CREATE INDEX IF NOT EXISTS idx_sd_outcome
                ON strategist_decisions(outcome);
            CREATE INDEX IF NOT EXISTS idx_sd_batch_id
                ON strategist_decisions(batch_id);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"v26 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_v25(conn: sqlite3.Connection) -> None:
    """v25 — widen strategist_decisions.decision_kind to also accept
    'AttemptDisproof'. Same point-in-time rebuild-and-copy as v23's
    strategist_decisions leg (columns unchanged since v22)."""
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='strategist_decisions'").fetchone()
    if chk and "'AttemptDisproof'" in (chk["sql"] or ""):
        return  # fresh DB from SCHEMA, or re-run

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategist_decisions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                problem             TEXT NOT NULL REFERENCES problems(name),
                triggered_at_tick   INTEGER NOT NULL,
                trigger_kind        TEXT NOT NULL
                                        CHECK(trigger_kind IN
                                              ('first_launch','pending_review',
                                               'routine','inject_batch_done')),
                decision_kind       TEXT NOT NULL
                                        CHECK(decision_kind IN
                                              ('Inject','ConfirmShelve','Reopen',
                                               'EmitDirective','InitializeDefs',
                                               'RequestUserAmend','Noop',
                                               'MarkDeliverable','Ingest',
                                               'FetchPaper','AttemptDisproof')),
                target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                brief               TEXT NULL DEFAULT NULL,
                reason              TEXT NULL DEFAULT NULL,
                payload             TEXT NOT NULL DEFAULT '{}',
                batch_id            TEXT NULL DEFAULT NULL,
                produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                                        ON DELETE SET NULL,
                produced_strategy_id INTEGER NULL DEFAULT NULL
                                        REFERENCES strategies(id) ON DELETE SET NULL,
                outcome             TEXT NULL DEFAULT NULL,
                outcome_detail      TEXT NULL DEFAULT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
            INSERT INTO _new_strategist_decisions
                (id, problem, triggered_at_tick, trigger_kind, decision_kind,
                 target_id, brief, reason, payload, batch_id, produced_goal_id,
                 produced_strategy_id, outcome, outcome_detail,
                 created_at, updated_at)
            SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
                   target_id, brief, reason, payload, batch_id, produced_goal_id,
                   produced_strategy_id, outcome, outcome_detail,
                   created_at, updated_at
            FROM strategist_decisions;
            DROP TABLE strategist_decisions;
            ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
            CREATE INDEX IF NOT EXISTS idx_sd_problem
                ON strategist_decisions(problem);
            CREATE INDEX IF NOT EXISTS idx_sd_outcome
                ON strategist_decisions(outcome);
            CREATE INDEX IF NOT EXISTS idx_sd_batch_id
                ON strategist_decisions(batch_id);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"v25 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_v19(conn: sqlite3.Connection) -> None:
    """v19 — widen `goals.kind` CHECK to also accept 'inductive'.
    SQLite cannot ALTER a CHECK; rebuild the table with the new clause,
    copy every row, swap (same pattern as phase 4 / 13 / 14).

    The DDL below is a point-in-time snapshot of the goals SCHEMA at
    v18 (all columns through the additive ALTER block: entry_kind /
    integrity_verified / alias_target_id / is_deliverable) — it must
    stay column-for-column identical to the SCHEMA constant, differing
    only by the widened CHECK. The INSERT column list is computed from
    the LIVE table: older DBs reach this step through the phase-2/4
    rebuilds, whose point-in-time snapshots predate late additive
    columns (`is_deliverable`) — those columns are re-added by the
    blind ALTER block only on the NEXT init_schema pass, so within this
    pass the live table may lack them. Missing columns take the new
    DDL's defaults (is_deliverable → 0), which is the correct backfill.

    Pre-condition: PRAGMA user_version < 19.
    Post-condition (caller sets user_version = 19):
      - goals.kind CHECK accepts 'inductive'
      - all rows + idx_goals_status preserved
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if chk and "'inductive'" in (chk["sql"] or ""):
        return  # CHECK already wide (fresh DB from SCHEMA, or re-run)

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem','def','structure',
                                               'class','inductive')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved','frozen','dead')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                is_deliverable INTEGER NOT NULL DEFAULT 0
                                CHECK(is_deliverable IN (0,1)),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            )""")
        new_cols = ["id", "problem", "slug", "lean_path", "statement",
                    "kind", "origin", "status", "depth", "attempts",
                    "entry_kind", "integrity_verified", "detached",
                    "alias_target_id", "is_deliverable",
                    "created_at", "updated_at"]
        live_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
        copy_cols = ", ".join(c for c in new_cols if c in live_cols)
        conn.execute(
            f"INSERT INTO _new_goals ({copy_cols})"
            f" SELECT {copy_cols} FROM goals")
        conn.executescript("""
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"v19 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_v23(conn: sqlite3.Connection) -> None:
    """v23 — three CHECK widens for the Scholar pipeline (paper v2):
    pipelines.kind / queue.kind gain 'Scholar'; strategist_decisions.
    decision_kind gains 'FetchPaper'. SQLite cannot ALTER a CHECK.

    * queue is TRANSIENT (swept per-scope at startup, refill re-derives)
      → dropped and recreated from the updated SCHEMA, no row copy.
      Migrations run before any daemon, so no live lease is lost.
    * pipelines / strategist_decisions are history → rebuild-and-copy
      (point-in-time snapshots of their v22 shapes, explicit column
      lists — physical order differs on ALTER-grown DBs).
    Idempotent via the in-DDL probes."""
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='pipelines'").fetchone()
    if chk and "'Scholar'" in (chk["sql"] or ""):
        return  # fresh DB from SCHEMA, or re-run

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_pipelines (
                id          TEXT PRIMARY KEY,
                kind        TEXT NOT NULL
                                CHECK(kind IN ('Builder','Backward','Verify',
                                               'Strategist','Forward',
                                               'Librarian','Scholar')),
                target_id   TEXT NOT NULL,
                target_kind TEXT NOT NULL
                                CHECK(target_kind IN ('Goal','Strategy',
                                                      'Problem')),
                status      TEXT NOT NULL
                                CHECK(status IN ('succeeded','failed')),
                outcome     TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                finished_at TEXT NOT NULL
            );
            INSERT INTO _new_pipelines
                (id, kind, target_id, target_kind, status, outcome,
                 started_at, finished_at)
            SELECT id, kind, target_id, target_kind, status, outcome,
                   started_at, finished_at
            FROM pipelines;
            DROP TABLE pipelines;
            ALTER TABLE _new_pipelines RENAME TO pipelines;

            DROP TABLE queue;
            CREATE TABLE queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                kind        TEXT NOT NULL
                                CHECK(kind IN ('Builder','Backward','Verify',
                                               'Strategist','Forward',
                                               'Librarian','Scholar')),
                target_id   TEXT NOT NULL,
                target_kind TEXT NOT NULL DEFAULT 'Goal'
                                CHECK(target_kind IN ('Goal','Strategy',
                                                      'Problem')),
                priority    INTEGER NOT NULL DEFAULT 0,
                decision_id INTEGER NULL DEFAULT NULL
                                REFERENCES strategist_decisions(id),
                problem     TEXT NOT NULL DEFAULT '',
                payload     TEXT,
                owner_pid   INTEGER,
                leased_at   TEXT,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE _new_strategist_decisions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                problem             TEXT NOT NULL REFERENCES problems(name),
                triggered_at_tick   INTEGER NOT NULL,
                trigger_kind        TEXT NOT NULL
                                        CHECK(trigger_kind IN
                                              ('first_launch','pending_review',
                                               'routine','inject_batch_done')),
                decision_kind       TEXT NOT NULL
                                        CHECK(decision_kind IN
                                              ('Inject','ConfirmShelve','Reopen',
                                               'EmitDirective','InitializeDefs',
                                               'RequestUserAmend','Noop',
                                               'MarkDeliverable','Ingest',
                                               'FetchPaper')),
                target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                brief               TEXT NULL DEFAULT NULL,
                reason              TEXT NULL DEFAULT NULL,
                payload             TEXT NOT NULL DEFAULT '{}',
                batch_id            TEXT NULL DEFAULT NULL,
                produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                                        ON DELETE SET NULL,
                produced_strategy_id INTEGER NULL DEFAULT NULL
                                        REFERENCES strategies(id) ON DELETE SET NULL,
                outcome             TEXT NULL DEFAULT NULL,
                outcome_detail      TEXT NULL DEFAULT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
            INSERT INTO _new_strategist_decisions
                (id, problem, triggered_at_tick, trigger_kind, decision_kind,
                 target_id, brief, reason, payload, batch_id, produced_goal_id,
                 produced_strategy_id, outcome, outcome_detail,
                 created_at, updated_at)
            SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
                   target_id, brief, reason, payload, batch_id, produced_goal_id,
                   produced_strategy_id, outcome, outcome_detail,
                   created_at, updated_at
            FROM strategist_decisions;
            DROP TABLE strategist_decisions;
            ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
            CREATE INDEX IF NOT EXISTS idx_sd_problem
                ON strategist_decisions(problem);
            CREATE INDEX IF NOT EXISTS idx_sd_outcome
                ON strategist_decisions(outcome);
            CREATE INDEX IF NOT EXISTS idx_sd_batch_id
                ON strategist_decisions(batch_id);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"v23 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _widen_goals_kind_check(conn: sqlite3.Connection,
                            kinds: "tuple[str, ...]") -> None:
    """The v19 live-column goals rebuild, generalized: rebuild `goals`
    with `kind CHECK(kind IN kinds)`. Probes on the NEWEST kind (last
    element) — present in the live DDL means the CHECK is already wide
    (fresh DB from SCHEMA, or re-run). All v19 caveats apply (see
    `_migrate_to_v19`): INSERT column list computed from the live table
    because phase-2/4 rebuild snapshots predate late additive columns.

    Callers are versioned steps; each passes the full kind tuple as of
    its version, so this function has no per-version state of its own."""
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    probe = f"'{kinds[-1]}'"
    if chk and probe in (chk["sql"] or ""):
        return
    kinds_sql = ",".join(f"'{k}'" for k in kinds)

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.execute(f"""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ({kinds_sql})),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved','frozen','dead')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                is_deliverable INTEGER NOT NULL DEFAULT 0
                                CHECK(is_deliverable IN (0,1)),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            )""")
        new_cols = ["id", "problem", "slug", "lean_path", "statement",
                    "kind", "origin", "status", "depth", "attempts",
                    "entry_kind", "integrity_verified", "detached",
                    "alias_target_id", "is_deliverable",
                    "created_at", "updated_at"]
        live_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
        copy_cols = ", ".join(c for c in new_cols if c in live_cols)
        conn.execute(
            f"INSERT INTO _new_goals ({copy_cols})"
            f" SELECT {copy_cols} FROM goals")
        conn.executescript("""
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"goals kind-CHECK widen left FK violations: "
                f"{fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase11(conn: sqlite3.Connection) -> None:
    """Phase 11 — widen `strategies.status` CHECK to accept 'stalled'.
    SQLite cannot ALTER a CHECK; rebuild the table with the new clause,
    copy rows, swap. Idempotent: skips when the CHECK is already wide.

    Pre-condition: PRAGMA user_version < 11.
    Post-condition (caller sets user_version = 11):
      - strategies.status CHECK accepts 'stalled'
      - All existing rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='strategies'"
    ).fetchone()
    # Table absent (fresh DB) → init_schema's CREATE already built the wide
    # CHECK; nothing to rebuild. Wide already → skip.
    if not chk or "'stalled'" in (chk["sql"] or ""):
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategies (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id      INTEGER NOT NULL REFERENCES goals(id),
                lean_path    TEXT    NOT NULL,
                scratch_path TEXT    NOT NULL DEFAULT '',
                status       TEXT    NOT NULL
                                 CHECK(status IN ('proposed','succeeded',
                                                  'dead','superseded',
                                                  'stalled')),
                proposal_md  TEXT    NOT NULL DEFAULT '',
                created_by   TEXT    NOT NULL,
                created_at   TEXT NOT NULL
            );
            INSERT INTO _new_strategies SELECT * FROM strategies;
            DROP TABLE strategies;
            ALTER TABLE _new_strategies RENAME TO strategies;
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 11 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase8(conn: sqlite3.Connection) -> None:
    """Phase 8 — widen `library_decls.lifecycle` CHECK to accept 'cleaned'.
    SQLite cannot ALTER a CHECK; rebuild the table with the new clause, copy
    rows, swap. Idempotent: skips when the CHECK is already wide.

    Pre-condition: PRAGMA user_version < 8.
    Post-condition (caller sets user_version = 8):
      - library_decls.lifecycle CHECK accepts 'cleaned'
      - All existing rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
        " AND name='library_decls'"
    ).fetchone()
    # Table absent (pre-Librarian DB) → init_schema's CREATE already built the
    # wide CHECK; nothing to rebuild. Wide already → skip.
    if not chk or "'cleaned'" in (chk["sql"] or ""):
        return
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_library_decls (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                problem         TEXT NOT NULL REFERENCES problems(name),
                slug            TEXT NOT NULL,
                source_goal_id  INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                                    ON DELETE SET NULL,
                verdict         TEXT NULL DEFAULT NULL,
                citation        TEXT NULL DEFAULT NULL,
                target_file     TEXT NULL DEFAULT NULL,
                target_name     TEXT NULL DEFAULT NULL,
                file_order      INTEGER NULL DEFAULT NULL,
                lifecycle       TEXT NOT NULL DEFAULT 'candidate'
                                    CHECK(lifecycle IN (
                                      'candidate','deduped','classified',
                                      'migrated','cleaned','dropped','cited')),
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_library_decls SELECT * FROM library_decls;
            DROP TABLE library_decls;
            ALTER TABLE _new_library_decls RENAME TO library_decls;
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 8 migration left FK violations: {fk_violations[:5]}")
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase7(conn: sqlite3.Connection) -> None:
    """Phase 7 — widen `pipelines.kind` and `queue.kind` CHECK to accept
    'Librarian'. SQLite cannot ALTER a CHECK constraint; rebuild each
    table with the new CHECK clause, copy rows, swap.

    Pre-condition: PRAGMA user_version < 7.

    Post-condition (caller sets user_version = 7):
      - pipelines.kind CHECK accepts 'Librarian'
      - queue.kind CHECK accepts 'Librarian'
      - All existing rows preserved unchanged
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # --- pipelines rebuild (skip if CHECK already wide) ---
        chk = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='pipelines'"
        ).fetchone()
        if not (chk and "'Librarian'" in (chk["sql"] or "")):
            conn.executescript("""
                CREATE TABLE _new_pipelines (
                    id          TEXT PRIMARY KEY,
                    kind        TEXT NOT NULL
                                    CHECK(kind IN ('Builder','Backward','Verify',
                                                   'Strategist','Forward',
                                                   'Librarian')),
                    target_id   TEXT NOT NULL,
                    target_kind TEXT NOT NULL
                                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
                    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
                    outcome     TEXT NOT NULL,
                    started_at  TEXT NOT NULL,
                    finished_at TEXT NOT NULL
                );
                INSERT INTO _new_pipelines SELECT * FROM pipelines;
                DROP TABLE pipelines;
                ALTER TABLE _new_pipelines RENAME TO pipelines;
                CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
            """)

        # --- queue rebuild (skip if CHECK already wide) ---
        chk = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table'"
            " AND name='queue'"
        ).fetchone()
        if not (chk and "'Librarian'" in (chk["sql"] or "")):
            conn.executescript("""
                CREATE TABLE _new_queue (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind        TEXT NOT NULL
                                    CHECK(kind IN ('Builder','Backward','Verify',
                                                   'Strategist','Forward',
                                                   'Librarian')),
                    target_id   TEXT NOT NULL,
                    target_kind TEXT NOT NULL DEFAULT 'Goal'
                                    CHECK(target_kind IN ('Goal','Strategy','Problem')),
                    priority    INTEGER NOT NULL DEFAULT 0,
                    decision_id INTEGER NULL DEFAULT NULL REFERENCES strategist_decisions(id),
                    created_at  TEXT NOT NULL
                );
                INSERT INTO _new_queue (id, kind, target_id, target_kind,
                    priority, decision_id, created_at)
                SELECT id, kind, target_id, target_kind,
                    priority, decision_id, created_at FROM queue;
                DROP TABLE queue;
                ALTER TABLE _new_queue RENAME TO queue;
                CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
            """)

        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 7 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase2(conn: sqlite3.Connection) -> None:
    """Phase 2 schema migration for pre-Phase 2 DBs.

    Rebuilds goals / pipelines / queue to widen CHECK constraints and
    add new columns. Backfills existing `shelved` rows into `disproved`
    based on dead_attempts.failure_reason = 'agent_infeasible'.

    Pre-condition: PRAGMA user_version < 2 AND goals table lacks the
    Phase 2 `detached` column (i.e. genuinely pre-Phase 2 schema).

    Post-condition (caller sets PRAGMA user_version = 2):
      - goals.origin CHECK accepts 'forward'
      - goals.status CHECK accepts 'pending_strategist_review', 'disproved'
      - goals has new `detached` column (default 0)
      - pipelines.kind CHECK accepts 'Strategist', 'Forward'
      - pipelines.target_kind CHECK accepts 'Problem'
      - queue.kind CHECK accepts 'Strategist', 'Forward'
      - queue has new `target_kind` column (default 'Goal') + `decision_id`
        column (NULL FK)

    Failure recovery: SQLite executescript implicit-commits between
    statements, so a mid-rebuild failure leaves the DB in an
    inconsistent state. Operator should `cp asterism.db
    asterism.db.pre_phase2_<UTC>` before first daemon start under
    Phase 2 code (per `docs/internal/archive/phase2_migration_plan.md §E`).
    """
    # PRAGMA foreign_keys cannot be set inside a transaction.
    # connect() leaves us at autocommit (isolation_level default).
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        # --- goals rebuild: extend origin/status CHECK + add detached ---
        # INSERT SELECT lists columns explicitly (new `detached` not in
        # source); it gets the DEFAULT 0 from _new_goals schema.
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals (id, problem, slug, lean_path, statement,
                kind, origin, status, depth, attempts, entry_kind,
                integrity_verified, alias_target_id, created_at, updated_at)
            SELECT id, problem, slug, lean_path, statement,
                kind, origin, status, depth, attempts, entry_kind,
                integrity_verified, alias_target_id, created_at, updated_at
            FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)

        # Backfill: existing 'shelved' rows whose latest decline gave a
        # counterexample (failure_reason='agent_infeasible') represent
        # the new 'disproved' semantic. Must run AFTER goals rebuild so
        # the new CHECK accepts 'disproved'. dead_attempts is intact
        # (no rebuild on it).
        conn.execute("""
            UPDATE goals SET status = 'disproved'
            WHERE status = 'shelved'
              AND id IN (
                SELECT DISTINCT target_id FROM dead_attempts
                WHERE target_kind = 'Goal'
                  AND failure_reason = 'agent_infeasible'
              )
        """)

        # --- pipelines rebuild: extend kind + target_kind CHECK ---
        conn.executescript("""
            CREATE TABLE _new_pipelines (
                id          TEXT PRIMARY KEY,
                kind        TEXT NOT NULL
                                CHECK(kind IN ('Builder','Backward','Verify',
                                               'Strategist','Forward')),
                target_id   TEXT NOT NULL,
                target_kind TEXT NOT NULL
                                CHECK(target_kind IN ('Goal','Strategy','Problem')),
                status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
                outcome     TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                finished_at TEXT NOT NULL
            );
            INSERT INTO _new_pipelines SELECT * FROM pipelines;
            DROP TABLE pipelines;
            ALTER TABLE _new_pipelines RENAME TO pipelines;
            CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
        """)

        # --- queue rebuild: extend kind CHECK + add target_kind, decision_id ---
        conn.executescript("""
            CREATE TABLE _new_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                kind        TEXT NOT NULL
                                CHECK(kind IN ('Builder','Backward','Verify',
                                               'Strategist','Forward')),
                target_id   TEXT NOT NULL,
                target_kind TEXT NOT NULL DEFAULT 'Goal'
                                CHECK(target_kind IN ('Goal','Strategy','Problem')),
                priority    INTEGER NOT NULL DEFAULT 0,
                decision_id INTEGER NULL DEFAULT NULL REFERENCES strategist_decisions(id),
                created_at  TEXT NOT NULL
            );
            INSERT INTO _new_queue (id, kind, target_id, priority, created_at)
            SELECT id, kind, target_id, priority, created_at FROM queue;
            DROP TABLE queue;
            ALTER TABLE _new_queue RENAME TO queue;
            CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
        """)

        # Validate FK integrity post-rebuild
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 2 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase4(conn: sqlite3.Connection) -> None:
    """Phase 4 — widen `goals.kind` CHECK to accept Forward non-theorem
    artifacts (`def`, `structure`, `class`). Rebuild required because
    SQLite cannot ALTER a CHECK constraint in place.

    Pre-condition: PRAGMA user_version < 4. Existing rows are preserved
    unchanged — pre-Phase 4 DBs only had `kind='theorem'` so the
    rebuild has no data-shape concerns.

    Post-condition (caller sets user_version = 4):
      - goals.kind CHECK accepts {'theorem','def','structure','class'}
      - All existing rows + indexes preserved
    """
    # Skip if widened CHECK already in place (fresh DB built from
    # current SCHEMA, or repeat migration).
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if chk and "'structure'" in (chk["sql"] or ""):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem','def',
                                               'structure','class')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals SELECT * FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 4 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase6(conn: sqlite3.Connection) -> None:
    """Phase 6 — widen `goals.status` CHECK to accept 'dead' (terminal
    for parent_needs_fix decline). Hard terminal but doesn't block dedupe
    (same statement may be valid under a different parent strategy).
    Same rebuild pattern as phase 5.

    Pre-condition: PRAGMA user_version < 6.

    Post-condition (caller sets user_version = 6):
      - goals.status CHECK accepts {'open','attempting','proved','shelved',
        'pending_strategist_review','disproved','frozen','dead'}
      - All existing rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if chk and "'dead'" in (chk["sql"] or ""):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem','def',
                                               'structure','class')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved','frozen','dead')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals SELECT * FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 6 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase5(conn: sqlite3.Connection) -> None:
    """Phase 5 — widen `goals.status` CHECK to accept 'frozen' (root
    pre-launch state). Same rebuild pattern as phase 4. Backfill: for
    every problem with bootstrap_done=0 flip its root goal's status from
    'open' to 'frozen' — the legacy bootstrap_done=0 condition is exactly
    the new frozen condition.

    Pre-condition: PRAGMA user_version < 5.

    Post-condition (caller sets user_version = 5):
      - goals.status CHECK accepts {'open','attempting','proved','shelved',
        'pending_strategist_review','disproved','frozen'}
      - Roots of bootstrap_done=0 problems are 'frozen'
      - All other rows preserved unchanged
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='goals'"
    ).fetchone()
    if chk and "'frozen'" in (chk["sql"] or ""):
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_goals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem     TEXT    NOT NULL REFERENCES problems(name),
                slug        TEXT    NOT NULL,
                lean_path   TEXT    NOT NULL UNIQUE,
                statement   TEXT    NOT NULL,
                kind        TEXT    NOT NULL DEFAULT 'theorem'
                                CHECK(kind IN ('theorem','def',
                                               'structure','class')),
                origin      TEXT    NOT NULL
                                CHECK(origin IN ('root','backward','forward')),
                status      TEXT    NOT NULL
                                CHECK(status IN ('open','attempting','proved',
                                                 'shelved',
                                                 'pending_strategist_review',
                                                 'disproved','frozen')),
                depth       INTEGER NOT NULL DEFAULT 0,
                attempts    INTEGER NOT NULL DEFAULT 0,
                entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                                CHECK(entry_kind IN ('Builder','Backward')),
                integrity_verified INTEGER NOT NULL DEFAULT 0
                                CHECK(integrity_verified IN (0,1)),
                detached    INTEGER NOT NULL DEFAULT 0
                                CHECK(detached IN (0,1)),
                alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                UNIQUE(problem, slug)
            );
            INSERT INTO _new_goals SELECT * FROM goals;
            DROP TABLE goals;
            ALTER TABLE _new_goals RENAME TO goals;
            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
        """)
        prob_cols = {r[1] for r in conn.execute(
            "PRAGMA table_info(problems)")}
        if "bootstrap_done" in prob_cols:
            conn.execute(
                "UPDATE goals SET status = 'frozen', updated_at = ? "
                " WHERE origin = 'root' AND status = 'open' "
                "   AND problem IN (SELECT name FROM problems "
                "                    WHERE bootstrap_done = 0)",
                (now(),),
            )
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 5 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase3(conn: sqlite3.Connection) -> None:
    """Phase 2.5 — widen strategist_decisions.trigger_kind CHECK to
    accept 'inject_batch_done'. SQLite cannot ALTER a CHECK constraint;
    rebuild the table with the new CHECK clause, copy rows, swap.

    Pre-condition: PRAGMA user_version < 3. The previous phase 2 ALTER
    TABLE ADD COLUMN block has already added `batch_id` to the live
    table (additive, no CHECK on that column), so the rebuild here only
    has to widen the trigger_kind CHECK and preserve every other column.

    Post-condition (caller sets user_version = 3):
      - strategist_decisions.trigger_kind CHECK accepts 'inject_batch_done'
      - idx_sd_batch_id index present (matches SCHEMA constant)
      - All existing rows preserved unchanged
    """
    # Skip if rebuild already happened (fresh DB built from current
    # SCHEMA has the widened CHECK + index already; this lets the
    # phase 3 guard be idempotent on those DBs).
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table'"
        " AND name = 'strategist_decisions'"
    ).fetchone()
    if chk and "inject_batch_done" in (chk["sql"] or ""):
        # CHECK already wide enough; just ensure the index exists.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sd_batch_id"
            " ON strategist_decisions(batch_id)")
        conn.commit()
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategist_decisions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                problem             TEXT NOT NULL REFERENCES problems(name),
                triggered_at_tick   INTEGER NOT NULL,
                trigger_kind        TEXT NOT NULL
                                        CHECK(trigger_kind IN
                                              ('first_launch','pending_review',
                                               'routine','inject_batch_done')),
                decision_kind       TEXT NOT NULL
                                        -- 'Reopen'/'InitializeDefs': LEGACY, never
                                        -- emitted now (see strategist.DECISION_KINDS);
                                        -- kept so pre-2026-05-28 rows stay valid.
                                        CHECK(decision_kind IN
                                              ('Inject','ConfirmShelve','Reopen',
                                               'EmitDirective','InitializeDefs',
                                               'RequestUserAmend','Noop')),
                target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                brief               TEXT NULL DEFAULT NULL,
                reason              TEXT NULL DEFAULT NULL,
                payload             TEXT NOT NULL DEFAULT '{}',
                batch_id            TEXT NULL DEFAULT NULL,
                outcome             TEXT NULL DEFAULT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
            INSERT INTO _new_strategist_decisions
                (id, problem, triggered_at_tick, trigger_kind, decision_kind,
                 target_id, brief, reason, payload, batch_id, outcome,
                 created_at, updated_at)
            SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
                   target_id, brief, reason, payload, batch_id, outcome,
                   created_at, updated_at
            FROM strategist_decisions;
            DROP TABLE strategist_decisions;
            ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
            CREATE INDEX IF NOT EXISTS idx_sd_problem
                ON strategist_decisions(problem);
            CREATE INDEX IF NOT EXISTS idx_sd_outcome
                ON strategist_decisions(outcome);
            CREATE INDEX IF NOT EXISTS idx_sd_batch_id
                ON strategist_decisions(batch_id);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 3 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase13(conn: sqlite3.Connection) -> None:
    """Phase 13 — widen strategist_decisions.decision_kind CHECK to accept
    'MarkDeliverable' (anchor+claim architecture). SQLite cannot ALTER a
    CHECK; rebuild the table with the new CHECK, copy every row, swap.

    The DDL below is a point-in-time snapshot of the strategist_decisions
    SCHEMA at v13 (all columns added through v12's additive ALTERs:
    produced_goal_id / produced_strategy_id / outcome_detail) — it must
    stay column-for-column identical to the SCHEMA constant, differing
    only by the widened CHECK. Idempotent: fresh DBs already carry the
    widened CHECK, so the probe short-circuits.

    Post-condition (caller sets user_version = 13):
      - decision_kind CHECK accepts 'MarkDeliverable'
      - all rows + indexes preserved
    """
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table'"
        " AND name = 'strategist_decisions'"
    ).fetchone()
    if chk and "MarkDeliverable" in (chk["sql"] or ""):
        return  # CHECK already wide (fresh DB from SCHEMA, or re-run)

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategist_decisions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                problem             TEXT NOT NULL REFERENCES problems(name),
                triggered_at_tick   INTEGER NOT NULL,
                trigger_kind        TEXT NOT NULL
                                        CHECK(trigger_kind IN
                                              ('first_launch','pending_review',
                                               'routine','inject_batch_done')),
                decision_kind       TEXT NOT NULL
                                        CHECK(decision_kind IN
                                              ('Inject','ConfirmShelve','Reopen',
                                               'EmitDirective','InitializeDefs',
                                               'RequestUserAmend','Noop',
                                               'MarkDeliverable')),
                target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                brief               TEXT NULL DEFAULT NULL,
                reason              TEXT NULL DEFAULT NULL,
                payload             TEXT NOT NULL DEFAULT '{}',
                batch_id            TEXT NULL DEFAULT NULL,
                produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                                        ON DELETE SET NULL,
                produced_strategy_id INTEGER NULL DEFAULT NULL
                                        REFERENCES strategies(id) ON DELETE SET NULL,
                outcome             TEXT NULL DEFAULT NULL,
                outcome_detail      TEXT NULL DEFAULT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
            INSERT INTO _new_strategist_decisions
                (id, problem, triggered_at_tick, trigger_kind, decision_kind,
                 target_id, brief, reason, payload, batch_id, produced_goal_id,
                 produced_strategy_id, outcome, outcome_detail,
                 created_at, updated_at)
            SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
                   target_id, brief, reason, payload, batch_id, produced_goal_id,
                   produced_strategy_id, outcome, outcome_detail,
                   created_at, updated_at
            FROM strategist_decisions;
            DROP TABLE strategist_decisions;
            ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
            CREATE INDEX IF NOT EXISTS idx_sd_problem
                ON strategist_decisions(problem);
            CREATE INDEX IF NOT EXISTS idx_sd_outcome
                ON strategist_decisions(outcome);
            CREATE INDEX IF NOT EXISTS idx_sd_batch_id
                ON strategist_decisions(batch_id);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 13 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_phase14(conn: sqlite3.Connection) -> None:
    """Phase 14 — widen strategist_decisions.decision_kind CHECK to also
    accept 'Ingest' (anchor+claim harvest trigger). Same point-in-time
    table-rebuild snapshot as v13 (all columns through v12's additive
    ALTERs), CHECK now carrying both 'MarkDeliverable' and 'Ingest'.
    Idempotent via the probe. Post: caller sets user_version = 14."""
    chk = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table'"
        " AND name = 'strategist_decisions'"
    ).fetchone()
    if chk and "'Ingest'" in (chk["sql"] or ""):
        return  # CHECK already carries 'Ingest'

    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript("""
            CREATE TABLE _new_strategist_decisions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                problem             TEXT NOT NULL REFERENCES problems(name),
                triggered_at_tick   INTEGER NOT NULL,
                trigger_kind        TEXT NOT NULL
                                        CHECK(trigger_kind IN
                                              ('first_launch','pending_review',
                                               'routine','inject_batch_done')),
                decision_kind       TEXT NOT NULL
                                        CHECK(decision_kind IN
                                              ('Inject','ConfirmShelve','Reopen',
                                               'EmitDirective','InitializeDefs',
                                               'RequestUserAmend','Noop',
                                               'MarkDeliverable','Ingest')),
                target_id           INTEGER NULL DEFAULT NULL REFERENCES goals(id),
                brief               TEXT NULL DEFAULT NULL,
                reason              TEXT NULL DEFAULT NULL,
                payload             TEXT NOT NULL DEFAULT '{}',
                batch_id            TEXT NULL DEFAULT NULL,
                produced_goal_id    INTEGER NULL DEFAULT NULL REFERENCES goals(id)
                                        ON DELETE SET NULL,
                produced_strategy_id INTEGER NULL DEFAULT NULL
                                        REFERENCES strategies(id) ON DELETE SET NULL,
                outcome             TEXT NULL DEFAULT NULL,
                outcome_detail      TEXT NULL DEFAULT NULL,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
            INSERT INTO _new_strategist_decisions
                (id, problem, triggered_at_tick, trigger_kind, decision_kind,
                 target_id, brief, reason, payload, batch_id, produced_goal_id,
                 produced_strategy_id, outcome, outcome_detail,
                 created_at, updated_at)
            SELECT id, problem, triggered_at_tick, trigger_kind, decision_kind,
                   target_id, brief, reason, payload, batch_id, produced_goal_id,
                   produced_strategy_id, outcome, outcome_detail,
                   created_at, updated_at
            FROM strategist_decisions;
            DROP TABLE strategist_decisions;
            ALTER TABLE _new_strategist_decisions RENAME TO strategist_decisions;
            CREATE INDEX IF NOT EXISTS idx_sd_problem
                ON strategist_decisions(problem);
            CREATE INDEX IF NOT EXISTS idx_sd_outcome
                ON strategist_decisions(outcome);
            CREATE INDEX IF NOT EXISTS idx_sd_batch_id
                ON strategist_decisions(batch_id);
        """)
        fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
        if fk_violations:
            raise RuntimeError(
                f"Phase 14 migration left FK violations: {fk_violations[:5]}"
            )
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_v42(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE problem_papers_v42 (
            problem    TEXT NOT NULL REFERENCES problems(name),
            paper_id   TEXT NOT NULL,
            origin     TEXT NOT NULL CHECK(origin IN ('manifest','scholar',
                'user','agent','strategist','adversary','formalizer',
                'librarian','presearch')),
            reason     TEXT NULL DEFAULT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (problem, paper_id)
        )""")
    n = conn.execute("INSERT INTO problem_papers_v42"
                     " SELECT * FROM problem_papers").rowcount
    conn.execute("DROP TABLE problem_papers")
    conn.execute("ALTER TABLE problem_papers_v42 RENAME TO problem_papers")
    if n:
        # Silent on fresh/empty DBs: cmd_status --json shares stdout.
        print(f"[v42] problem_papers rebuilt with the seat-family origin"
              f" CHECK ({n} binding(s) carried)", flush=True)


def _migrate_to_v43(conn: sqlite3.Connection) -> None:
    """Widen strategist_decisions.trigger_kind CHECK to accept 'stall'.

    Derives the rebuild DDL from the LIVE table's sqlite_master entry
    instead of re-spelling the schema: this table has been rebuilt
    several times (v3, ...) and a hand-copied column list here would
    silently freeze whichever vintage the author looked at. String-
    widening the CHECK enum in the table's own DDL is vintage-proof."""
    # Self-heal an interrupted prior attempt: the CREATE below commits
    # piecemeal (this ladder is not one transaction), so a crash
    # mid-step leaves `_sd_v43` behind and the NEXT attempt died on
    # "already exists" (2026-08-24, the crash that exposed the
    # migration race).
    conn.execute("DROP TABLE IF EXISTS _sd_v43")
    # FK enforcement OFF for the rebuild (the v42 rebuild's own
    # precedent, right above): with `connect()`'s foreign_keys=ON the
    # DROP of a table other rows reference is an IntegrityError — the
    # second crash of the same boarding day (2026-08-24; the fixture
    # tests used raw sqlite3, whose FK default is OFF, and missed it).
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table'"
            " AND name = 'strategist_decisions'").fetchone()
        sql = (row["sql"] or "") if row else ""
        if not sql or "'stall'" in sql:
            return  # fresh DB from current SCHEMA already carries it
        for old, new in (
            ("'inject_batch_done','audit'",
             "'inject_batch_done','audit','stall'"),
            ("'inject_batch_done'", "'inject_batch_done','stall'"),
        ):
            if old in sql:
                new_sql = sql.replace(old, new, 1)
                break
        else:
            raise RuntimeError(
                "v43: strategist_decisions CHECK enum not found in its DDL"
                " — refusing to guess; inspect the table's sqlite_master"
                " sql")
        new_sql = re.sub(r"CREATE TABLE\s+\"?strategist_decisions\"?",
                         "CREATE TABLE _sd_v43", new_sql, count=1)
        indexes = [r["sql"] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index'"
            " AND tbl_name = 'strategist_decisions' AND sql IS NOT NULL")]
        conn.execute(new_sql)
        n = conn.execute(
            "INSERT INTO _sd_v43 SELECT * FROM strategist_decisions").rowcount
        conn.execute("DROP TABLE strategist_decisions")
        conn.execute("ALTER TABLE _sd_v43 RENAME TO strategist_decisions")
        for s in indexes:
            conn.execute(s)
        if n:
            print(f"[v43] strategist_decisions rebuilt with 'stall' in the"
                  f" trigger_kind CHECK ({n} row(s) carried)", flush=True)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_to_v44(conn: sqlite3.Connection) -> None:
    """strategy_subgoals.link_kind — edge provenance (minted vs cited).

    Additive ADD COLUMN (no rebuild). Backfill classifies existing
    edges structurally: a strategy can only CITE a goal that already
    existed before the strategy row itself, while a MINTED sub-goal is
    inserted at commit, after its strategy row — so
    `goal.created_at < strategy.created_at` identifies cited edges.
    Ties (same-instant timestamps cannot occur across the two inserts,
    but defend anyway) default to 'minted', which is the pre-v44
    behaviour for every reader."""
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(strategy_subgoals)")}
    if "link_kind" in cols:
        return  # fresh DB from current SCHEMA already carries it
    conn.execute(
        "ALTER TABLE strategy_subgoals ADD COLUMN link_kind TEXT NOT NULL"
        " DEFAULT 'minted' CHECK(link_kind IN ('minted','cited'))")
    n = conn.execute(
        "UPDATE strategy_subgoals SET link_kind = 'cited'"
        " WHERE EXISTS (SELECT 1 FROM strategies s, goals g"
        "                WHERE s.id = strategy_subgoals.strategy_id"
        "                  AND g.id = strategy_subgoals.subgoal_id"
        "                  AND g.created_at < s.created_at)").rowcount
    if n:
        print(f"[v44] strategy_subgoals.link_kind backfilled: {n} cited"
              f" edge(s) reclassified (rest minted)", flush=True)


def _migrate_to_v45(conn: sqlite3.Connection) -> None:
    """Widen strategist_decisions.trigger_kind CHECK to accept
    'routine_fired' — the v43 rebuild, one value further. Derives the
    DDL from the live sqlite_master entry (vintage-proof), self-heals an
    interrupted prior attempt, runs with FK enforcement off."""
    conn.execute("DROP TABLE IF EXISTS _sd_v45")
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table'"
            " AND name = 'strategist_decisions'").fetchone()
        sql = (row["sql"] or "") if row else ""
        if not sql or "'routine_fired'" in sql:
            return  # fresh DB from current SCHEMA already carries it
        if "'stall'" not in sql:
            raise RuntimeError(
                "v45: strategist_decisions CHECK enum has no 'stall' —"
                " v43 did not run; refusing to guess")
        new_sql = sql.replace("'stall'", "'stall','routine_fired'", 1)
        new_sql = re.sub(r"CREATE TABLE\s+\"?strategist_decisions\"?",
                         "CREATE TABLE _sd_v45", new_sql, count=1)
        indexes = [r["sql"] for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index'"
            " AND tbl_name = 'strategist_decisions' AND sql IS NOT NULL")]
        conn.execute(new_sql)
        n = conn.execute(
            "INSERT INTO _sd_v45 SELECT * FROM strategist_decisions").rowcount
        conn.execute("DROP TABLE strategist_decisions")
        conn.execute("ALTER TABLE _sd_v45 RENAME TO strategist_decisions")
        for s in indexes:
            conn.execute(s)
        if n:
            print(f"[v45] strategist_decisions rebuilt with 'routine_fired'"
                  f" in the trigger_kind CHECK ({n} row(s) carried)",
                  flush=True)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
