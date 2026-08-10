"""Phase 2 DB schema migration tests.

Covers `docs/internal/phase2_migration_plan.md §D` — forward migration,
idempotency, preservation of pre-Phase 2 data, shelved→disproved
backfill rule.

Strategy: build a fixture DB at pre-Phase 2 schema via hand-rolled SQL,
seed representative rows, run `init_schema` (which performs the
migration), and assert post-conditions.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db


# ---------------------------------------------------------------------
# Pre-Phase 2 schema fixture (verbatim from before this migration)
# ---------------------------------------------------------------------

_PRE_PHASE2_SCHEMA = """
CREATE TABLE IF NOT EXISTS problems (
    name           TEXT PRIMARY KEY,
    manifest_path  TEXT NOT NULL,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    problem     TEXT    NOT NULL REFERENCES problems(name),
    slug        TEXT    NOT NULL,
    lean_path   TEXT    NOT NULL UNIQUE,
    statement   TEXT    NOT NULL,
    kind        TEXT    NOT NULL DEFAULT 'theorem'
                    CHECK(kind IN ('theorem')),
    origin      TEXT    NOT NULL
                    CHECK(origin IN ('root','backward')),
    status      TEXT    NOT NULL
                    CHECK(status IN ('open','attempting','proved','shelved')),
    depth       INTEGER NOT NULL DEFAULT 0,
    attempts    INTEGER NOT NULL DEFAULT 0,
    entry_kind  TEXT    NOT NULL DEFAULT 'Builder'
                    CHECK(entry_kind IN ('Builder','Backward')),
    integrity_verified INTEGER NOT NULL DEFAULT 0
                    CHECK(integrity_verified IN (0,1)),
    alias_target_id INTEGER NULL DEFAULT NULL REFERENCES goals(id),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(problem, slug)
);

CREATE TABLE IF NOT EXISTS strategies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id      INTEGER NOT NULL REFERENCES goals(id),
    lean_path    TEXT    NOT NULL,
    scratch_path TEXT    NOT NULL DEFAULT '',
    status       TEXT    NOT NULL
                     CHECK(status IN ('proposed','succeeded','dead','superseded')),
    proposal_md  TEXT    NOT NULL DEFAULT '',
    created_by   TEXT    NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_subgoals (
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    subgoal_id  INTEGER NOT NULL REFERENCES goals(id),
    position    INTEGER NOT NULL,
    PRIMARY KEY (strategy_id, subgoal_id)
);

CREATE TABLE IF NOT EXISTS pipelines (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK(target_kind IN ('Goal','Strategy')),
    status      TEXT NOT NULL CHECK(status IN ('succeeded','failed')),
    outcome     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dead_attempts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id       INTEGER NOT NULL,
    target_kind     TEXT NOT NULL,
    pipeline_id     TEXT NOT NULL REFERENCES pipelines(id),
    failure_reason  TEXT NOT NULL,
    failure_detail  TEXT,
    proposal_md     TEXT,
    artifacts       TEXT,
    ts              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT NOT NULL CHECK(kind IN ('Builder','Backward','Verify')),
    target_id   TEXT NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON pipelines(status);
CREATE INDEX IF NOT EXISTS idx_queue_priority ON queue(priority DESC, id ASC);
"""


def _make_pre_phase2_db(tmp_path: Path) -> Path:
    """Create a tmp DB at pre-Phase 2 schema with representative rows."""
    db_path = tmp_path / "asterism.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_PRE_PHASE2_SCHEMA)
    # PRAGMA user_version stays 0 (default)

    ts = "2026-05-18T00:00:00+00:00"
    # Seed: 2 problems, each with a root + 2 sub-goals + a strategy
    for prob in ("alpha", "beta"):
        # Pre-Phase-2 schema intentionally has no bootstrap_done column — the
        # migration this test exercises ADDs it. Keep this INSERT in the
        # legacy 3-column form.
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at)"
            " VALUES (?, ?, ?)", (prob, f"Problems/{prob}/Manifest.md", ts))
        # Root goal — proved (alpha) or attempting (beta)
        root_status = "proved" if prob == "alpha" else "attempting"
        integrity = 1 if prob == "alpha" else 0
        conn.execute(
            "INSERT INTO goals (id, problem, slug, lean_path, statement,"
            " kind, origin, status, depth, attempts, entry_kind,"
            " integrity_verified, created_at, updated_at)"
            " VALUES (NULL, ?, 'main', ?, 'T', 'theorem', 'root', ?,"
            " 0, 0, 'Backward', ?, ?, ?)",
            (prob, f"Problems/{prob}/Root.lean", root_status, integrity,
             ts, ts))
    # Sub-goal under alpha: shelved with agent_infeasible decline (→ disproved)
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " integrity_verified, created_at, updated_at)"
        " VALUES ('alpha', 'sub_infeasible',"
        " 'Problems/alpha/proofs/L_sub_infeasible.lean', 'T',"
        " 'theorem', 'backward', 'shelved', 1, 3, 'Builder', 0, ?, ?)",
        (ts, ts))
    # Sub-goal under alpha: shelved with agent_shelved decline (stays shelved)
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " integrity_verified, created_at, updated_at)"
        " VALUES ('alpha', 'sub_shelved',"
        " 'Problems/alpha/proofs/L_sub_shelved.lean', 'T',"
        " 'theorem', 'backward', 'shelved', 1, 3, 'Builder', 0, ?, ?)",
        (ts, ts))
    # Sub-goal under beta: open
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, entry_kind,"
        " integrity_verified, created_at, updated_at)"
        " VALUES ('beta', 'sub_open',"
        " 'Problems/beta/proofs/L_sub_open.lean', 'T',"
        " 'theorem', 'backward', 'open', 1, 0, 'Builder', 0, ?, ?)",
        (ts, ts))

    # Strategy for alpha
    conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (1, 'Problems/alpha/Root.lean',"
        " 'Problems/alpha/proofs/_strategy_s1.lean', 'succeeded',"
        " '', 'backward', ?)",
        (ts,))
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (1, 3, 1)")  # sub_infeasible

    # Pipeline + dead_attempts: sub_infeasible has agent_infeasible decline
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at)"
        " VALUES ('p1', 'Builder', '3', 'Goal', 'failed',"
        " 'failed', ?, ?)", (ts, ts))
    conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, ts)"
        " VALUES (3, 'Goal', 'p1', 'agent_infeasible',"
        " 'counterexample shown', ?)", (ts,))

    # Queue: one Backward entry on beta's sub_open
    conn.execute(
        "INSERT INTO queue (kind, target_id, priority, created_at)"
        " VALUES ('Backward', '5', 0, ?)", (ts,))

    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------

def test_migration_runs_on_pre_phase2_db(tmp_path: Path) -> None:
    """Forward migration path (D.1): pre-Phase 2 DB → init_schema →
    Phase 2 schema in place with PRAGMA user_version at the latest
    (Phase 2.5 bumped this from 2 to 3 for the strategist_decisions
    trigger_kind CHECK widening + batch_id column)."""
    db_path = _make_pre_phase2_db(tmp_path)

    # Before migration: user_version = 0, goals lacks 'detached'
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 0
    goals_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
    assert "detached" not in goals_cols
    assert "bootstrap_done" not in {
        r[1] for r in conn.execute("PRAGMA table_info(problems)")
    }
    conn.close()

    # Run migration
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    # Post: PRAGMA user_version at latest (bumped to 11 in phase 11).
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 39

    # New columns present
    goals_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
    assert "detached" in goals_cols
    problems_cols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
    assert "bootstrap_done" in problems_cols
    assert "strategist_directive" in problems_cols
    assert "last_strategist_at" in problems_cols
    queue_cols = {r[1] for r in conn.execute("PRAGMA table_info(queue)")}
    assert "target_kind" in queue_cols
    assert "decision_id" in queue_cols

    # New table present
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='strategist_decisions'"
    ).fetchall()
    assert len(rows) == 1

    # Phase 2.5 — batch_id column + inject_batch_done trigger_kind
    sd_cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(strategist_decisions)")}
    assert "batch_id" in sd_cols
    sd_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='strategist_decisions'"
    ).fetchone()[0]
    assert "inject_batch_done" in sd_sql

    # Phase 4 — goals.kind CHECK widened to def / structure / class
    goals_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='goals'"
    ).fetchone()[0]
    for kw in ("'def'", "'structure'", "'class'"):
        assert kw in goals_sql

    # New CHECK values accepted on goals
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts,"
        " integrity_verified, created_at, updated_at)"
        " VALUES ('alpha', 'fwd_lemma',"
        " 'Problems/alpha/proofs/L_fwd_lemma.lean', 'T',"
        " 'theorem', 'forward', 'open', 0, 0, 0,"
        " '2026-05-18T00:00:00+00:00', '2026-05-18T00:00:00+00:00')")
    conn.execute(
        "UPDATE goals SET status='pending_strategist_review' WHERE slug='sub_open'")
    conn.commit()

    # FK integrity
    fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
    assert fk_violations == [], f"FK violations: {fk_violations}"
    conn.close()


def test_shelved_split_by_decline_directive(tmp_path: Path) -> None:
    """B.4 / D.1 backfill: existing 'shelved' rows whose dead_attempts
    carry failure_reason='agent_infeasible' become 'disproved'; others
    stay 'shelved'."""
    db_path = _make_pre_phase2_db(tmp_path)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    # sub_infeasible had failure_reason='agent_infeasible' → 'disproved'
    row = conn.execute(
        "SELECT status FROM goals WHERE slug='sub_infeasible'"
    ).fetchone()
    assert row["status"] == "disproved"

    # sub_shelved had no agent_infeasible dead_attempt → stays 'shelved'
    row = conn.execute(
        "SELECT status FROM goals WHERE slug='sub_shelved'"
    ).fetchone()
    assert row["status"] == "shelved"
    conn.close()


def test_proved_root_preserved(tmp_path: Path) -> None:
    """D.3: existing proved root (status='proved', integrity_verified=1)
    is preserved by migration; db.root_proved still returns True."""
    db_path = _make_pre_phase2_db(tmp_path)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    row = conn.execute(
        "SELECT status, integrity_verified, detached"
        " FROM goals WHERE problem='alpha' AND slug='main'"
    ).fetchone()
    assert row["status"] == "proved"
    assert row["integrity_verified"] == 1
    assert row["detached"] == 0  # new column defaults to 0

    assert db.root_proved(conn, problem="alpha") is True
    assert db.root_proved(conn, problem="beta") is False
    conn.close()


def test_migration_idempotent(tmp_path: Path) -> None:
    """D.2: running init_schema twice on the same DB does not fail and
    leaves identical row counts. Tests that the user_version gate
    prevents re-running the rebuild."""
    db_path = _make_pre_phase2_db(tmp_path)

    # First run
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    counts1 = {
        "goals": conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0],
        "strategies": conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0],
        "pipelines": conn.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0],
        "queue": conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0],
        "dead_attempts": conn.execute("SELECT COUNT(*) FROM dead_attempts").fetchone()[0],
    }
    conn.close()

    # Second run — should be no-op (PRAGMA user_version already at latest)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    counts2 = {
        "goals": conn.execute("SELECT COUNT(*) FROM goals").fetchone()[0],
        "strategies": conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0],
        "pipelines": conn.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0],
        "queue": conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0],
        "dead_attempts": conn.execute("SELECT COUNT(*) FROM dead_attempts").fetchone()[0],
    }
    assert counts1 == counts2

    # Schema version at latest; idempotent re-run leaves it unchanged.
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 39
    conn.close()


def test_v19_widens_goals_kind_to_inductive(tmp_path: Path) -> None:
    """v19: goals.kind CHECK gains 'inductive'. The pre-Phase-2 fixture
    exercises the real rebuild: the phase-4 step rebuilds goals with the
    OLD kind CHECK, so the v19 probe does not short-circuit and the
    table-rebuild path runs — rows preserved, new kind accepted, CHECK
    still enforced for unknown kinds."""
    db_path = _make_pre_phase2_db(tmp_path)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    slugs_before = {
        r[0] for r in conn.execute("SELECT slug FROM goals")
    }
    db.init_schema(conn)

    # Rebuild preserved every row.
    slugs_after = {
        r[0] for r in conn.execute("SELECT slug FROM goals")
    }
    assert slugs_before <= slugs_after

    # CHECK now carries 'inductive'.
    goals_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='goals'"
    ).fetchone()[0]
    assert "'inductive'" in goals_sql

    # New kind accepted end-to-end.
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts,"
        " integrity_verified, created_at, updated_at)"
        " VALUES ('alpha', 'fwd_ind',"
        " 'Problems/alpha/proofs/L_fwd_ind.lean', 'Type',"
        " 'inductive', 'forward', 'proved', 0, 0, 0,"
        " '2026-07-05T00:00:00+00:00', '2026-07-05T00:00:00+00:00')")
    conn.commit()

    # CHECK still rejects unknown kinds (widen, not drop).
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO goals (problem, slug, lean_path, statement,"
            " kind, origin, status, depth, attempts,"
            " integrity_verified, created_at, updated_at)"
            " VALUES ('alpha', 'fwd_bogus',"
            " 'Problems/alpha/proofs/L_fwd_bogus.lean', 'T',"
            " 'axiom', 'forward', 'open', 0, 0, 0,"
            " '2026-07-05T00:00:00+00:00', '2026-07-05T00:00:00+00:00')")

    fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
    assert fk_violations == [], f"FK violations: {fk_violations}"
    conn.close()


def test_v20_widens_goals_kind_to_instance(tmp_path: Path) -> None:
    """v20: goals.kind CHECK gains 'instance' (same generalized rebuild
    as v19 — the pre-Phase-2 fixture exercises it for real)."""
    db_path = _make_pre_phase2_db(tmp_path)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    goals_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='goals'"
    ).fetchone()[0]
    assert "'instance'" in goals_sql

    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts,"
        " integrity_verified, created_at, updated_at)"
        " VALUES ('alpha', 'fwd_inst',"
        " 'Problems/alpha/proofs/L_fwd_inst.lean', 'Monoid Bar',"
        " 'instance', 'forward', 'proved', 0, 0, 0,"
        " '2026-07-05T00:00:00+00:00', '2026-07-05T00:00:00+00:00')")
    conn.commit()
    fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
    assert fk_violations == [], f"FK violations: {fk_violations}"
    conn.close()


def test_v23_scholar_and_fetchpaper_widens(tmp_path: Path) -> None:
    """v23 (paper v2): pipelines/queue kind CHECK gain 'Scholar';
    strategist_decisions gains 'FetchPaper'; problem_papers exists.
    The pre-Phase-2 fixture exercises the real rebuild chain."""
    db_path = _make_pre_phase2_db(tmp_path)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    for table in ("pipelines", "queue"):
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name=?", (table,)
        ).fetchone()[0]
        assert "'Scholar'" in sql, table
    sd_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name='strategist_decisions'"
    ).fetchone()[0]
    assert "'FetchPaper'" in sd_sql
    # History preserved through the rebuild (fixture seeds pipelines).
    assert conn.execute("SELECT COUNT(*) FROM pipelines").fetchone()[0] > 0

    # problem_papers + binding helpers round-trip.
    assert db.bind_paper(conn, problem="alpha", paper_id="abc123",
                         origin="manifest") is True
    assert db.bind_paper(conn, problem="alpha", paper_id="abc123",
                         origin="scholar") is False  # idempotent, first wins
    assert db.bind_paper(conn, problem="alpha", paper_id="def456",
                         origin="scholar", reason="cited [X]") is True
    rows = db.paper_bindings(conn, "alpha")
    assert [r["paper_id"] for r in rows] == ["abc123", "def456"]
    assert rows[0]["origin"] == "manifest"
    assert db.scholar_fetch_count(conn, "alpha") == 1
    fk_violations = list(conn.execute("PRAGMA foreign_key_check"))
    assert fk_violations == [], f"FK violations: {fk_violations}"
    conn.close()


def test_fresh_db_skips_rebuild_and_sets_version(tmp_path: Path) -> None:
    """Fresh DB (created via current SCHEMA) skips _migrate_to_phase2
    (detected via 'detached' column already present) but still bumps
    PRAGMA user_version to the latest."""
    db_path = tmp_path / "fresh.db"
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    # New schema present
    goals_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
    assert "detached" in goals_cols
    # Version set
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 39
    # strategist_decisions table created
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name='strategist_decisions'"
    ).fetchall()
    assert len(rows) == 1
    conn.close()


def test_v28_manifest_history_carryover(tmp_path: Path) -> None:
    """v28: `manifest_history` (lived <1 day) generalizes to
    `user_file_history` — existing rows carry over as Manifest.md
    observations, the old table drops, version lands at 28."""
    db_path = tmp_path / "v27.db"
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)", (db.now(),))
    # Rewind to the v27 shape: old table with a row, new table absent.
    conn.execute("DROP TABLE user_file_history")
    conn.execute("""
        CREATE TABLE manifest_history (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL,
            sha     TEXT NOT NULL,
            body    TEXT NOT NULL,
            seen_at TEXT NOT NULL
        )""")
    conn.execute(
        "INSERT INTO manifest_history (problem, sha, body, seen_at)"
        " VALUES ('p', 'abc123', '# p ask', ?)", (db.now(),))
    conn.execute("PRAGMA user_version = 27")
    conn.commit()

    from Tooling.state import db_migrations
    db_migrations.apply(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 39
    rows = conn.execute(
        "SELECT problem, file, sha, body, source FROM user_file_history"
    ).fetchall()
    assert len(rows) == 1
    r = rows[0]
    assert (str(r["problem"]), str(r["file"]), str(r["sha"]),
            str(r["source"])) == ("p", "Manifest.md", "abc123", "observed")
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name='manifest_history'").fetchone() is None
    conn.close()


def test_v29_problem_state_backfill(tmp_path: Path) -> None:
    """v29 (problem FSM): `problems.state` backfills from the legacy
    carriers — signoff-pending ingest → 'ingest_signoff', bare
    ingested_at → 'ingested', unresolved RequestUserAmend →
    'awaiting_human', else 'active'. (The ALTER branch is exercised on
    real pre-v29 DBs; SQLite can't DROP a CHECKed column to rewind it
    here, so this pins the backfill + version step.)"""
    db_path = tmp_path / "v28.db"
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    ts = db.now()
    for name in ("p_active", "p_await", "p_signoff", "p_ingested"):
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at)"
            " VALUES (?, ?, ?)", (name, f"Problems/{name}/Manifest.md", ts))
    conn.execute(
        "UPDATE problems SET ingested_at = ?, ingest_signoff_pending = 1"
        " WHERE name = 'p_signoff'", (ts,))
    conn.execute(
        "UPDATE problems SET ingested_at = ? WHERE name = 'p_ingested'",
        (ts,))
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, outcome, created_at,"
        " updated_at) VALUES ('p_await', 0, 'routine',"
        " 'RequestUserAmend', '{}', 'awaiting_human', ?, ?)", (ts, ts))
    conn.execute("PRAGMA user_version = 28")
    conn.commit()

    from Tooling.state import db_migrations
    db_migrations.apply(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 39
    states = {str(r["name"]): str(r["state"]) for r in conn.execute(
        "SELECT name, state FROM problems")}
    assert states == {"p_active": "active", "p_await": "awaiting_human",
                      "p_signoff": "ingest_signoff",
                      "p_ingested": "ingested"}
    conn.close()


def test_phase2_check_values_rejected_pre_migration(tmp_path: Path) -> None:
    """Sanity: pre-migration DB rejects new CHECK values (e.g. origin='forward').
    Confirms the fixture DB really does have the old CHECK constraints."""
    db_path = _make_pre_phase2_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO goals (problem, slug, lean_path, statement,"
            " kind, origin, status, depth, attempts, entry_kind,"
            " integrity_verified, created_at, updated_at)"
            " VALUES ('alpha', 'fwd', 'x.lean', 'T',"
            " 'theorem', 'forward', 'open', 0, 0, 'Backward', 0,"
            " '2026-05-18T00:00:00+00:00', '2026-05-18T00:00:00+00:00')")
    conn.close()


def test_new_columns_have_correct_defaults(tmp_path: Path) -> None:
    """Migrated rows get the documented defaults for new columns."""
    db_path = _make_pre_phase2_db(tmp_path)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    # goals.detached default 0
    for row in conn.execute("SELECT detached FROM goals"):
        assert row["detached"] == 0

    # problems columns defaults
    for row in conn.execute(
        "SELECT bootstrap_done, strategist_directive, last_strategist_at"
        " FROM problems"
    ):
        assert row["bootstrap_done"] == 0
        assert row["strategist_directive"] is None
        assert row["last_strategist_at"] is None

    # queue.target_kind defaults to 'Goal'; queue.decision_id NULL
    for row in conn.execute("SELECT target_kind, decision_id FROM queue"):
        assert row["target_kind"] == "Goal"
        assert row["decision_id"] is None
    conn.close()


def test_strategist_decisions_table_usable_post_migration(tmp_path: Path) -> None:
    """strategist_decisions accepts representative Phase 2 row shapes."""
    db_path = _make_pre_phase2_db(tmp_path)

    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)

    ts = "2026-05-18T01:00:00+00:00"
    # Inject decision (target_id NULL, brief set)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " outcome, created_at, updated_at)"
        " VALUES ('alpha', 5, 'routine', 'Inject', NULL,"
        " '## Need\\n...', NULL, '{\"pipeline\": \"Forward\"}', NULL, ?, ?)",
        (ts, ts))
    # ConfirmShelve decision (target_id set, reason)
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " outcome, created_at, updated_at)"
        " VALUES ('alpha', 6, 'pending_review', 'ConfirmShelve', 3,"
        " NULL, 'truly dead', '{}', NULL, ?, ?)",
        (ts, ts))
    conn.commit()

    rows = conn.execute(
        "SELECT decision_kind, target_id FROM strategist_decisions"
        " ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["decision_kind"] == "Inject"
    assert rows[0]["target_id"] is None
    assert rows[1]["decision_kind"] == "ConfirmShelve"
    assert rows[1]["target_id"] == 3

    # CHECK rejects unknown decision_kind
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, payload, created_at, updated_at)"
            " VALUES ('alpha', 7, 'routine', 'BogusKind', '{}', ?, ?)",
            (ts, ts))
    conn.close()


# --- connect-time auto-migration of a stale-but-populated DB (#81) ---

def test_current_user_version_matches_init_schema(tmp_path):
    # Drift guard: init_schema must leave user_version at _CURRENT_USER_VERSION.
    # If a new phase bumps the version but forgets the constant, this fails.
    conn = db.connect(tmp_path / "v.db")
    db.init_schema(conn)
    assert (conn.execute("PRAGMA user_version").fetchone()[0]
            == db._CURRENT_USER_VERSION)
    conn.close()


def test_connect_leaves_fresh_db_uninitialized(tmp_path):
    # A FRESH DB (no tables) is NOT auto-initialized by connect — the caller's
    # explicit init_schema still owns first-time setup.
    conn = db.connect(tmp_path / "fresh.db")
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "goals" not in tables
    conn.close()


def test_connect_auto_migrates_stale_populated_db(tmp_path):
    # A populated DB whose user_version is behind must be auto-migrated on
    # connect (the v6->v9 incident), so no caller operates on a stale schema.
    p = tmp_path / "stale.db"
    c0 = db.connect(p)
    db.init_schema(c0)                       # fresh → CURRENT
    c0.execute("PRAGMA user_version = 6")    # pretend it's an old on-disk DB
    c0.commit()
    c0.close()
    c1 = db.connect(p)                       # stale + populated → auto-migrate
    assert (c1.execute("PRAGMA user_version").fetchone()[0]
            == db._CURRENT_USER_VERSION)
    cols = {r[1] for r in c1.execute("PRAGMA table_info(library_decls)")}
    assert "reopen_note" in cols             # phase-9 column present after migrate
    c1.close()


def test_v21_creates_spawn_usage_table(tmp_path, monkeypatch):
    """v21 (frontend charter 5-2): per-spawn token accounting table. Fresh
    init gets it via the migration chain; columns match the writer."""
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(spawn_usage)")}
    assert {"pipeline_id", "kind", "problem", "input_tokens",
            "output_tokens", "cache_read_tokens", "cache_new_tokens",
            "turns", "wall_sec", "ts"} <= cols
    conn.close()


def test_record_spawn_usage_roundtrip(tmp_path):
    """agent._record_spawn_usage reads the provider parser-state usage
    block and lands one row; no parser state / empty usage = no row and
    no error (telemetry never fails a spawn)."""
    import json
    from Tooling.agent import runtime as rt
    ws = tmp_path
    conn = db.connect(ws / "asterism.db")
    db.init_schema(conn)
    conn.close()
    attempts = ws / ".attempts" / "pid-usage-1"
    attempts.mkdir(parents=True)
    pdir = ws / "Problems" / "Logic" / "toy"
    pdir.mkdir(parents=True)
    # no parser state -> no row, no crash
    rt._record_spawn_usage(kind="builder", attempts_dir=attempts,
                           problem_dir=pdir, wall_sec=1.0)
    (attempts / "_parser_state.json").write_text(json.dumps({
        "usage": {"input_tokens": 10, "output_tokens": 200,
                  "cache_read_input_tokens": 3000,
                  "cache_creation_input_tokens": 400, "turns": 5}}),
        encoding="utf-8")
    rt._record_spawn_usage(kind="builder", attempts_dir=attempts,
                           problem_dir=pdir, wall_sec=12.5)
    conn = db.connect(ws / "asterism.db")
    rows = conn.execute("SELECT * FROM spawn_usage").fetchall()
    conn.close()
    assert len(rows) == 1
    r = rows[0]
    assert r["pipeline_id"] == "pid-usage-1"
    assert r["kind"] == "builder"
    assert r["problem"] == "Logic.toy"          # dotted, not the leaf
    assert r["output_tokens"] == 200 and r["turns"] == 5
    assert r["wall_sec"] == 12.5


def test_connect_readonly_reads_but_cannot_write(tmp_path):
    """Charter 5-5: the web layer's only legal DB entry. mode=ro makes
    writes impossible at the engine level; current-version DBs open fine."""
    import pytest
    p = tmp_path / "asterism.db"
    conn = db.connect(p)
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('p', 'm', ?)", (db.now(),))
    conn.commit()
    conn.close()
    ro = db.connect_readonly(p)
    assert ro.execute("SELECT count(*) FROM problems").fetchone()[0] == 1
    with pytest.raises(Exception):          # sqlite3.OperationalError
        ro.execute("INSERT INTO problems (name, manifest_path, created_at)"
                   " VALUES ('q', 'm', 'now')")
    ro.close()


def test_connect_readonly_refuses_stale_schema(tmp_path):
    """A behind DB raises SchemaBehind (with both versions) instead of
    auto-migrating - connect()'s auto-migrate is a WRITE a read-only
    consumer must never perform."""
    import pytest
    p = tmp_path / "asterism.db"
    conn = db.connect(p)
    db.init_schema(conn)
    conn.execute("PRAGMA user_version = 17")     # simulate stale
    conn.commit()
    conn.close()
    with pytest.raises(db.SchemaBehind) as ei:
        db.connect_readonly(p)
    assert ei.value.found == 17
    assert ei.value.expected == db._CURRENT_USER_VERSION


def test_v22_review_snapshot_roundtrip(tmp_path, monkeypatch):
    """v22 (charter 5-4): review snapshot columns + set/get/load. The
    Ingest commit writes it while the gateway is warm; readers consume
    the stored JSON instead of paying a cold closure per view."""
    import json
    from Tooling.quality import review as review_mod
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('p', 'm', ?)", (db.now(),))
    conn.commit()
    assert review_mod.load_review_snapshot(conn, "p") is None
    payload = {"deliverables": [{"fq": "Problems.p.x", "ok": True}],
               "union_count": 3}
    db.set_review_snapshot(conn, "p", json.dumps(payload))
    got = review_mod.load_review_snapshot(conn, "p")
    assert got is not None
    data, at = got
    assert data == payload and at
    # unparseable / wrong-shape snapshots degrade to None (live compute)
    db.set_review_snapshot(conn, "p", "{not json")
    assert review_mod.load_review_snapshot(conn, "p") is None
    conn.close()


def test_cmd_review_snapshot_path_never_touches_gateway(tmp_path,
                                                        monkeypatch):
    """Charter 5-4 load rule: with a stored snapshot, `asterism review
    <p>` renders without warming the gateway (GET must not be a heavy
    op; the CLI default mirrors the API)."""
    import argparse, json
    from Tooling.core.cli import cmd_review
    from Tooling.lsp import lifecycle as gl
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('p', 'm', ?)", (db.now(),))
    payload = {"deliverables": [
        {"fq": "Problems.p.x", "problem": "p", "slug": "x", "ok": True,
         "error": None, "kind": "claim", "module": None, "paper": "",
         "anchors": [], "claims": [], "folded": 0}], "union_count": 0}
    db.set_review_snapshot(conn, "p", json.dumps(payload))
    conn.commit()
    conn.close()

    def _boom(*a, **k):
        raise AssertionError("snapshot path must not warm the gateway")
    monkeypatch.setattr(gl, "start_gateway", _boom)
    rc = cmd_review(argparse.Namespace(problem="p", fresh=False))
    assert rc == 0


def test_v26_trigger_kind_accepts_audit(tmp_path, monkeypatch):
    """v26 — strategist_decisions.trigger_kind CHECK includes 'audit'.
    The trigger is retired at runtime (2026-07-25, merged into
    routine), but historic rows keep the value, so fresh SCHEMA and
    the rebuild migration must both still accept it."""
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('p', 'm', ?)", (db.now(),))
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, payload, created_at, updated_at)"
        " VALUES ('p', 0, 'audit', 'EmitDirective', '{}', ?, ?)",
        (db.now(), db.now()))
    conn.commit()
    row = conn.execute("SELECT trigger_kind FROM strategist_decisions"
                       " WHERE trigger_kind='audit'").fetchone()
    assert row is not None
    conn.close()
