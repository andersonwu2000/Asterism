"""Phase 2 DB schema migration tests.

Covers `docs/internal/phase2_migration_plan.md §D` — forward migration,
idempotency, preservation of pre-Phase 2 data, shelved→disproved
backfill rule.

Strategy: build a fixture DB at pre-Phase 2 schema via hand-rolled SQL,
seed representative rows, run `init_schema` (which performs the
migration), and assert post-conditions.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db

# The terminal `user_version` this file pins steps with
# `db._CURRENT_USER_VERSION`. 48→49 2026-09-02: HID §3.7's `Signal`
# widens `human_commands.kind`, and SQLite takes a widened CHECK only
# as a table rebuild — hence a version step. 49→50 2026-09-03:
# `strategist_decisions.report_carried_at` — additive, and since v15
# additive columns ship as version steps too. 52→53 2026-09-06:
# `strategist_decisions.infra_deaths` — same channel, and it is what
# bounds re-queueing a request whose worker died on infra.


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
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54

    # New columns present
    goals_cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
    assert "detached" in goals_cols
    problems_cols = {r[1] for r in conn.execute("PRAGMA table_info(problems)")}
    assert "bootstrap_done" in problems_cols
    assert "strategist_directive" in problems_cols
    assert "last_strategist_at" in problems_cols
    # v40 — Manifest retirement: manifest_path dropped, user_word added.
    assert "manifest_path" not in problems_cols
    assert "user_word" in problems_cols
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
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
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
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
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
        "INSERT INTO problems (name, created_at)"
        " VALUES ('p', ?)", (db.now(),))
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

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
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
            "INSERT INTO problems (name, created_at)"
            " VALUES (?, ?)", (name, ts))
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

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
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
    conn.execute("INSERT INTO problems (name, created_at)"
                 " VALUES ('p', ?)", (db.now(),))
    conn.commit()
    conn.close()
    ro = db.connect_readonly(p)
    assert ro.execute("SELECT count(*) FROM problems").fetchone()[0] == 1
    with pytest.raises(Exception):          # sqlite3.OperationalError
        ro.execute("INSERT INTO problems (name, created_at)"
                   " VALUES ('q', 'now')")
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
    conn.execute("INSERT INTO problems (name, created_at)"
                 " VALUES ('p', ?)", (db.now(),))
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
    conn.execute("INSERT INTO problems (name, created_at)"
                 " VALUES ('p', ?)", (db.now(),))
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
    conn.execute("INSERT INTO problems (name, created_at)"
                 " VALUES ('p', ?)", (db.now(),))
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


def test_v41_retires_stranded_manifest_amend_rows(tmp_path, monkeypatch):
    """v41 — a pre-v40 `RequestUserAmend` row still awaiting_human with
    payload file='Manifest.md' is unresolvable after the retirement:
    `amend._ALLOWED_FILES` no longer admits the target and the check
    sits BEFORE both the accept and reject paths, so the Inbox card was
    immortal and its problem paused forever (live-DB row 213,
    Topology.brouwer_fixed_point, ruled moot 2026-08-19). The migration
    auto-rejects exactly those rows and lifts the pause; historical
    resolved rows and awaiting rows on live targets stay untouched."""
    import json as _json
    monkeypatch.chdir(tmp_path)
    conn = db.connect()
    db.init_schema(conn)
    ts = db.now()
    for name in ("p_stranded", "p_live", "p_done"):
        conn.execute("INSERT INTO problems (name, created_at)"
                     " VALUES (?, ?)", (name, ts))
    def _rua(problem, file, outcome):
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, payload, outcome, created_at,"
            " updated_at) VALUES (?, 0, 'routine', 'RequestUserAmend',"
            " ?, ?, ?, ?)",
            (problem, _json.dumps({"file": file, "proposed_body": "x",
                                   "question": "q"}), outcome, ts, ts))
    _rua("p_stranded", "Manifest.md", "awaiting_human")
    _rua("p_live", "charter", "awaiting_human")
    _rua("p_done", "Manifest.md", "accepted")
    conn.execute("UPDATE problems SET state = 'awaiting_human'"
                 " WHERE name IN ('p_stranded', 'p_live')")
    conn.execute("PRAGMA user_version = 40")
    conn.commit()

    from Tooling.state import db_migrations
    db_migrations.apply(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
    rows = {str(r["problem"]): (str(r["outcome"]),
                                str(r["outcome_detail"] or ""))
            for r in conn.execute(
                "SELECT problem, outcome, outcome_detail"
                " FROM strategist_decisions"
                " WHERE decision_kind = 'RequestUserAmend'")}
    assert rows["p_stranded"][0] == "rejected"
    assert "v41" in rows["p_stranded"][1]
    assert rows["p_live"] == ("awaiting_human", "")      # live target stays
    assert rows["p_done"][0] == "accepted"               # history untouched
    states = {str(r["name"]): str(r["state"]) for r in conn.execute(
        "SELECT name, state FROM problems")}
    assert states["p_stranded"] == "active"    # pause lifted
    assert states["p_live"] == "awaiting_human"  # still legitimately held
    conn.close()


def test_v43_widens_trigger_kind_check_from_the_live_ddl(tmp_path):
    """v43 rebuilds strategist_decisions from its OWN sqlite_master DDL
    (vintage-proof — the table has been rebuilt several times and a
    hand-copied column list would freeze one vintage). After it, 'stall'
    inserts pass, old rows survive, indexes survive, and a second run
    is a no-op."""
    import sqlite3 as _sqlite3
    from Tooling.state import db_migrations as m
    conn = _sqlite3.connect(str(tmp_path / "old.db"))
    conn.row_factory = _sqlite3.Row
    # FK ON, matching db.connect() — the raw-sqlite3 default (OFF) let
    # the DROP-of-a-referenced-table crash ship (2026-08-24); the
    # referencing row makes this fixture honest.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE problems (name TEXT PRIMARY KEY);
        CREATE TABLE strategist_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL REFERENCES problems(name),
            trigger_kind TEXT NOT NULL CHECK(trigger_kind IN
                ('first_launch','pending_review','routine',
                 'inject_batch_done','audit')),
            decision_kind TEXT NOT NULL);
        CREATE TABLE queue_like (
            id INTEGER PRIMARY KEY,
            decision_id INTEGER REFERENCES strategist_decisions(id));
        CREATE INDEX idx_sd_problem ON strategist_decisions(problem);
        INSERT INTO problems VALUES ('p');
        INSERT INTO strategist_decisions
            (problem, trigger_kind, decision_kind)
            VALUES ('p', 'inject_batch_done', 'Inject');
        INSERT INTO queue_like VALUES (1, 1);
    """)
    conn.execute("PRAGMA foreign_keys = ON")
    m._migrate_to_v43(conn)
    conn.execute(
        "INSERT INTO strategist_decisions"
        " (problem, trigger_kind, decision_kind)"
        " VALUES ('p', 'stall', 'Inject')")
    rows = [r["trigger_kind"] for r in conn.execute(
        "SELECT trigger_kind FROM strategist_decisions ORDER BY id")]
    assert rows == ["inject_batch_done", "stall"]
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index'"
        " AND name='idx_sd_problem'").fetchone()
    m._migrate_to_v43(conn)  # idempotent
    conn.close()


def test_v44_link_kind_backfill_classifies_cited_edges(tmp_path):
    """v44 adds strategy_subgoals.link_kind and backfills structurally:
    a CITED (reused) sibling predates its strategy row, a MINTED
    sub-goal is inserted after it. The 2026-08-25 leak shape — a
    redispatch strategy citing an older sibling — must land 'cited';
    ordinary decomposition edges stay 'minted'. Idempotent."""
    import sqlite3 as _sqlite3
    from Tooling.state import db_migrations as m
    conn = _sqlite3.connect(str(tmp_path / "old.db"))
    conn.row_factory = _sqlite3.Row
    conn.executescript("""
        CREATE TABLE goals (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE strategies (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE strategy_subgoals (
            strategy_id INTEGER NOT NULL,
            subgoal_id  INTEGER NOT NULL,
            position    INTEGER NOT NULL,
            PRIMARY KEY (strategy_id, subgoal_id));
        -- old sibling, minted long before either strategy
        INSERT INTO goals VALUES (10, '2026-08-23T23:51:00+00:00');
        -- s1 decomposes: its sub-goal is inserted AFTER the row
        INSERT INTO strategies VALUES (1, '2026-08-24T13:57:00+00:00');
        INSERT INTO goals VALUES (11, '2026-08-24T14:28:00+00:00');
        INSERT INTO strategy_subgoals VALUES (1, 11, 0);
        -- s2 redispatch cites the OLD sibling (the leak edge)
        INSERT INTO strategies VALUES (2, '2026-08-25T00:33:00+00:00');
        INSERT INTO strategy_subgoals VALUES (2, 10, 0);
    """)
    m._migrate_to_v44(conn)
    kinds = {(r["strategy_id"], r["subgoal_id"]): r["link_kind"]
             for r in conn.execute(
                 "SELECT strategy_id, subgoal_id, link_kind"
                 " FROM strategy_subgoals")}
    assert kinds == {(1, 11): "minted", (2, 10): "cited"}
    m._migrate_to_v44(conn)  # idempotent — column probe short-circuits
    conn.close()


def test_v43_self_heals_an_interrupted_attempt(tmp_path):
    """The ladder is not one transaction: a crash mid-v43 leaves the
    _sd_v43 staging table behind, and the NEXT attempt died on
    'already exists' (2026-08-24 — the crash that exposed the
    migration race). The step must drop the orphan and finish."""
    import sqlite3 as _sqlite3
    from Tooling.state import db_migrations as m
    conn = _sqlite3.connect(str(tmp_path / "old.db"))
    conn.row_factory = _sqlite3.Row
    conn.executescript("""
        CREATE TABLE problems (name TEXT PRIMARY KEY);
        CREATE TABLE strategist_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL REFERENCES problems(name),
            trigger_kind TEXT NOT NULL CHECK(trigger_kind IN
                ('first_launch','inject_batch_done')),
            decision_kind TEXT NOT NULL);
        CREATE TABLE _sd_v43 (leftover INTEGER);  -- interrupted attempt
        INSERT INTO problems VALUES ('p');
        INSERT INTO strategist_decisions
            (problem, trigger_kind, decision_kind)
            VALUES ('p', 'inject_batch_done', 'Inject');
    """)
    m._migrate_to_v43(conn)
    conn.execute(
        "INSERT INTO strategist_decisions"
        " (problem, trigger_kind, decision_kind)"
        " VALUES ('p', 'stall', 'Inject')")
    assert conn.execute(
        "SELECT count(*) FROM strategist_decisions").fetchone()[0] == 2
    assert not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='_sd_v43'").fetchone()
    conn.close()


def test_concurrent_migrators_serialize_on_the_file_mutex(tmp_path):
    """connect() auto-migrates on EVERY stale connection and a daemon
    boot opens several (main + gateway subprocess): two racers both
    built _sd_v43 and the loser took the daemon down 4s after start
    (2026-08-24). apply() must serialize cross-connection; the loser
    re-reads the bumped version inside the lock and no-ops."""
    import sqlite3 as _sqlite3
    import threading as _th
    from Tooling.state import db, db_migrations as m
    path = tmp_path / "race.db"
    seed = _sqlite3.connect(str(path))
    seed.row_factory = _sqlite3.Row
    db.init_schema(seed)                      # full current schema (v43)
    # regress ONLY the v43 surface: old-CHECK strategist_decisions +
    # user_version 42, so both racers must run the real table rebuild
    seed.executescript("""
        DROP TABLE strategist_decisions;
        CREATE TABLE strategist_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL REFERENCES problems(name),
            trigger_kind TEXT NOT NULL CHECK(trigger_kind IN
                ('first_launch','inject_batch_done')),
            decision_kind TEXT NOT NULL);
        PRAGMA user_version = 42;
    """)
    seed.close()

    started = _th.Barrier(2)
    errors: list = []

    def migrate():
        conn = _sqlite3.connect(str(path), timeout=30)
        conn.row_factory = _sqlite3.Row
        try:
            started.wait(timeout=10)
            m.apply(conn)
            conn.commit()
        except Exception as e:  # noqa: BLE001 — the assertion target
            errors.append(e)
        finally:
            conn.close()

    ts = [_th.Thread(target=migrate) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=120)
    assert not errors, f"concurrent apply must not race: {errors}"
    check = _sqlite3.connect(str(path))
    assert (check.execute("PRAGMA user_version").fetchone()[0]
            == db._CURRENT_USER_VERSION)
    check.close()


def test_v45_widens_trigger_kind_check_with_routine_fired(tmp_path):
    """v45 — the routine wake is an audit; a fired audit seats an action
    wake recorded as trigger_kind 'routine_fired'. Same live-DDL rebuild
    as v43, one value further; old rows and indexes survive; idempotent."""
    import sqlite3 as _sqlite3
    from Tooling.state import db_migrations as m
    conn = _sqlite3.connect(str(tmp_path / "old.db"))
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE problems (name TEXT PRIMARY KEY);
        CREATE TABLE strategist_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL REFERENCES problems(name),
            trigger_kind TEXT NOT NULL CHECK(trigger_kind IN
                ('first_launch','pending_review','routine',
                 'inject_batch_done','audit','stall')),
            decision_kind TEXT NOT NULL);
        CREATE INDEX idx_sd_problem ON strategist_decisions(problem);
        INSERT INTO problems VALUES ('p');
        INSERT INTO strategist_decisions
            (problem, trigger_kind, decision_kind)
            VALUES ('p', 'stall', 'Inject');
    """)
    m._migrate_to_v45(conn)
    conn.execute(
        "INSERT INTO strategist_decisions"
        " (problem, trigger_kind, decision_kind)"
        " VALUES ('p', 'routine_fired', 'ConfirmShelve')")
    rows = [r["trigger_kind"] for r in conn.execute(
        "SELECT trigger_kind FROM strategist_decisions ORDER BY id")]
    assert rows == ["stall", "routine_fired"]
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index'"
        " AND name='idx_sd_problem'").fetchone()
    m._migrate_to_v45(conn)  # idempotent
    conn.close()


# ---------------------------------------------------------------------
# v48 — the human interface (human_interface_design.md §3.1-§3.4)
# ---------------------------------------------------------------------

def _rewind_to_v47(conn: sqlite3.Connection) -> None:
    """Undo exactly the v48 surface on a current-schema DB so a following
    `init_schema` runs the real forward step. The FK child goes first:
    SQLite refuses to drop a parent table while a live column still
    references it.

    The `trigger_kind` CHECK is rewound too (2026-09-02). Dropping the
    `actor` column alone left `'human'` in the enum, so the forward
    step's rebuild short-circuited on its own probe and NO fixture ever
    executed the `DROP TABLE strategist_decisions` every real disk takes
    — the blind spot that let the FK-armed rebuild ship."""
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("ALTER TABLE problems DROP COLUMN project")
    conn.execute("ALTER TABLE problems DROP COLUMN ingest_report")
    conn.execute("ALTER TABLE strategist_decisions DROP COLUMN actor")
    conn.execute("ALTER TABLE programme_revisions DROP COLUMN summary")
    conn.executescript("DROP TABLE human_commands; DROP TABLE projects;")
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table'"
        " AND name = 'strategist_decisions'").fetchone()[0]
    idx = [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'index'"
        " AND tbl_name = 'strategist_decisions' AND sql IS NOT NULL")]
    # The SCHEMA text carries `'human'` in a COMMENT as well as in the
    # enum, and the forward step's probe is a substring test — so the
    # comments go too, or the rewind is a no-op the probe cannot see.
    sql = "\n".join(ln for ln in sql.splitlines()
                    if not ln.strip().startswith("--"))
    sql = sql.replace("'routine_fired','human'", "'routine_fired'")
    assert "'human'" not in sql, "rewind did not remove 'human' from the enum"
    conn.execute(re.sub(
        r"CREATE TABLE\s+\"?strategist_decisions\"?", "CREATE TABLE _sd_v47",
        sql, count=1))
    conn.execute("INSERT INTO _sd_v47 SELECT * FROM strategist_decisions")
    conn.execute("DROP TABLE strategist_decisions")
    conn.execute("ALTER TABLE _sd_v47 RENAME TO strategist_decisions")
    for s in idx:
        conn.execute(s)
    conn.execute("PRAGMA user_version = 47")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def _v47_db(path: Path, problems: tuple = ()) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)
    for name in problems:
        conn.execute("INSERT INTO problems (name, created_at)"
                     " VALUES (?, ?)", (name, db.now()))
    _rewind_to_v47(conn)
    return conn


def test_v48_backfills_every_problem_into_a_project(tmp_path: Path) -> None:
    """§3.1 backfill: a dotted problem name defaults into a Project named
    by its FIRST segment, a dotless one into a Project of its own name,
    and the referenced `projects` rows are minted by the backfill itself
    — after it no problem row is left project-less."""
    conn = _v47_db(tmp_path / "v47.db",
                   ("Erdos.p1", "Erdos.p10", "union_closed"))
    db.init_schema(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
    assert {str(r["name"]): str(r["project"]) for r in conn.execute(
        "SELECT name, project FROM problems")} == {
        "Erdos.p1": "Erdos", "Erdos.p10": "Erdos",
        "union_closed": "union_closed"}
    assert {str(r["name"]) for r in conn.execute(
        "SELECT name FROM projects")} == {"Erdos", "union_closed"}
    assert list(conn.execute("PRAGMA foreign_key_check")) == []
    conn.close()


def test_v48_completes_on_a_populated_disk(tmp_path: Path) -> None:
    """The shape every real workspace has, and the one no fixture had.

    The backfill writes rows, and Python's sqlite3 opens a transaction on
    the first DML statement. `PRAGMA foreign_keys = OFF` is a SILENT
    no-op inside a transaction, so the rebuild that follows reaches
    `DROP TABLE strategist_decisions` with the constraints still armed;
    the implicit `DELETE FROM` then trips `queue.decision_id` (NO ACTION)
    and the whole step dies with `FOREIGN KEY constraint failed` —
    leaving the disk one version short, with `programme_revisions.summary`
    (added AFTER the rebuild) never created."""
    conn = _v47_db(tmp_path / "pop.db", ("Erdos.p1",))
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, created_at, updated_at)"
        " VALUES ('Erdos.p1', 0, 'routine', 'Inject', ?, ?)",
        (db.now(), db.now()))
    did = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.execute(
        "INSERT INTO queue (kind, target_id, decision_id, problem,"
        " created_at) VALUES ('Formalizer', '1', ?, 'Erdos.p1', ?)",
        (did, db.now()))
    conn.commit()

    db.init_schema(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
    assert "summary" in {r[1] for r in conn.execute(
        "PRAGMA table_info(programme_revisions)")}
    assert int(conn.execute(
        "SELECT decision_id FROM queue").fetchone()[0]) == did
    assert list(conn.execute("PRAGMA foreign_key_check")) == []
    conn.close()


def test_v48_decision_rebuild_keeps_ids_and_defaults_actor(tmp_path) -> None:
    """v48 rebuilds strategist_decisions for the 'human' trigger_kind (the
    v45 live-DDL rebuild, one value further) and appends `actor`. Carried
    rows keep their ids and read as the machine's own; the new CHECKs
    admit a human row and reject an unknown actor; indexes survive;
    the step is idempotent."""
    import sqlite3 as _sqlite3
    from Tooling.state import db_migrations as m
    conn = _sqlite3.connect(str(tmp_path / "old.db"))
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE problems (name TEXT PRIMARY KEY);
        CREATE TABLE strategist_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL REFERENCES problems(name),
            trigger_kind TEXT NOT NULL CHECK(trigger_kind IN
                ('first_launch','pending_review','routine',
                 'inject_batch_done','audit','stall','routine_fired')),
            decision_kind TEXT NOT NULL);
        CREATE INDEX idx_sd_problem ON strategist_decisions(problem);
        INSERT INTO problems VALUES ('p');
        INSERT INTO strategist_decisions
            (id, problem, trigger_kind, decision_kind)
            VALUES (41, 'p', 'stall', 'ConfirmShelve');
    """)
    m._v48_rebuild_strategist_decisions(conn)

    old = conn.execute(
        "SELECT id, actor FROM strategist_decisions").fetchall()
    assert [(r["id"], r["actor"]) for r in old] == [(41, "strategist")]
    conn.execute(
        "INSERT INTO strategist_decisions"
        " (problem, trigger_kind, decision_kind, actor)"
        " VALUES ('p', 'human', 'ConfirmShelve', 'human')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO strategist_decisions"
            " (problem, trigger_kind, decision_kind, actor)"
            " VALUES ('p', 'human', 'ConfirmShelve', 'operator')")
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index'"
        " AND name='idx_sd_problem'").fetchone()
    m._v48_rebuild_strategist_decisions(conn)  # idempotent
    assert conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions").fetchone()[0] == 2
    conn.close()


def test_v48_human_commands_idempotency_key_is_unique(tmp_path) -> None:
    """§3.3: the queue's replay defence is the UNIQUE idempotency_key —
    a re-POSTed command collides instead of enqueuing twice."""
    conn = sqlite3.connect(str(tmp_path / "hc.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('p', ?)",
                 (db.now(),))
    ins = ("INSERT INTO human_commands (problem, kind, payload,"
           " idempotency_key, status, created_at)"
           " VALUES ('p', 'ConfirmShelve', '{}', 'k1', 'queued', ?)")
    conn.execute(ins, (db.now(),))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(ins, (db.now(),))
    conn.close()


def test_v48_migrated_db_matches_a_fresh_one(tmp_path: Path) -> None:
    """Both directions of the completion condition: a v47-shaped DB
    migrated forward and a fresh `init_schema` DB end at the same
    user_version and the same column shape on every table v48 touches —
    including the two new tables' DDL."""
    fresh = sqlite3.connect(str(tmp_path / "fresh.db"), timeout=30)
    fresh.row_factory = sqlite3.Row
    db.init_schema(fresh)
    old = _v47_db(tmp_path / "old.db", ("Erdos.p1",))
    db.init_schema(old)

    def shape(conn, table):
        return [(r[1], r[2], r[3], r[4], r[5])
                for r in conn.execute(f"PRAGMA table_info({table})")]

    # Column ORDER is load-bearing on strategist_decisions (the rebuild
    # copies with SELECT *) and free everywhere else, so it is pinned as a
    # list here and as a set for programme_revisions — whose order is
    # vintage-dependent by construction: `last_words` is added by the
    # UNVERSIONED post-ladder block, i.e. after v48 on a fresh DB and
    # before it on a disk that already ran the old code.
    for table in ("problems", "strategist_decisions", "projects",
                  "human_commands"):
        assert shape(old, table) == shape(fresh, table), table
    assert (sorted(shape(old, "programme_revisions"))
            == sorted(shape(fresh, "programme_revisions")))
    for table in ("projects", "human_commands"):
        q = ("SELECT sql FROM sqlite_master WHERE type='table'"
             " AND name = ?")
        assert (old.execute(q, (table,)).fetchone()[0]
                == fresh.execute(q, (table,)).fetchone()[0]), table
    assert (old.execute("PRAGMA user_version").fetchone()[0]
            == fresh.execute("PRAGMA user_version").fetchone()[0]
            == db._CURRENT_USER_VERSION)
    old.close()
    fresh.close()


# ---------------------------------------------------------------------
# v49 — `Signal` joins human_commands.kind (human_interface_design §3.7)
# ---------------------------------------------------------------------

def _rewind_to_v49_predecessor(conn: sqlite3.Connection) -> None:
    """Undo exactly v49 on a current-schema DB: rebuild `human_commands`
    with the v48 CHECK (no 'Signal') and step the version back.

    A rebuild, not a hand-written DDL: the forward step's probe is a
    substring test on the LIVE sqlite_master text, so a rewind the probe
    cannot see is no fixture at all — the blind spot `_rewind_to_v47`
    was written to close (2026-09-02)."""
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table'"
        " AND name = 'human_commands'").fetchone()[0]
    sql = sql.replace("'Inject','Signal'", "'Inject'")
    assert "'Signal'" not in sql, "rewind did not remove 'Signal'"
    conn.execute(re.sub(r"CREATE TABLE\s+\"?human_commands\"?",
                        "CREATE TABLE _hc_v48", sql, count=1))
    conn.execute("INSERT INTO _hc_v48 SELECT * FROM human_commands")
    conn.execute("DROP TABLE human_commands")
    conn.execute("ALTER TABLE _hc_v48 RENAME TO human_commands")
    conn.execute("PRAGMA user_version = 48")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


_HC_INSERT = (
    "INSERT INTO human_commands (problem, kind, payload,"
    " idempotency_key, status, created_at) VALUES ('p', ?, '{}', ?,"
    " 'queued', ?)")


def test_v49_carries_the_queue_and_admits_a_signal(tmp_path: Path) -> None:
    """§3.7: the kill signal is a `human_commands.kind`, and SQLite cannot
    widen a CHECK in place — so v49 rebuilds the table. The queue is live
    state (a person's queued command must not evaporate under a version
    step), so the rows are carried; and the value the whole migration
    exists for is admitted afterwards, refused before."""
    conn = sqlite3.connect(str(tmp_path / "v48.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('p', ?)",
                 (db.now(),))
    conn.execute(_HC_INSERT, ("ConfirmShelve", "k1", db.now()))
    conn.commit()
    _rewind_to_v49_predecessor(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(_HC_INSERT, ("Signal", "k-sig-v48", db.now()))
    conn.rollback()

    db.init_schema(conn)

    assert conn.execute("PRAGMA user_version").fetchone()[0] == 54
    rows = conn.execute(
        "SELECT id, kind, idempotency_key, status FROM human_commands"
    ).fetchall()
    assert [(r["kind"], r["idempotency_key"], r["status"]) for r in rows] \
        == [("ConfirmShelve", "k1", "queued")]
    conn.execute(_HC_INSERT, ("Signal", "k-sig", db.now()))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(_HC_INSERT, ("Telepathy", "k-nope", db.now()))
    conn.rollback()
    assert list(conn.execute("PRAGMA foreign_key_check")) == []
    conn.close()


def test_v49_keeps_the_unique_key_and_the_foreign_keys(
        tmp_path: Path) -> None:
    """The rebuild must carry the table's CONSTRAINTS, not just its rows:
    the UNIQUE idempotency_key is the queue's whole replay defence (§3.3)
    and the two FKs are what make a receipt point at something."""
    conn = sqlite3.connect(str(tmp_path / "v48b.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('p', ?)",
                 (db.now(),))
    conn.commit()
    _rewind_to_v49_predecessor(conn)
    db.init_schema(conn)

    conn.execute(_HC_INSERT, ("Signal", "dup", db.now()))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(_HC_INSERT, ("Signal", "dup", db.now()))
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO human_commands (problem, kind, payload,"
            " idempotency_key, status, created_at) VALUES ('ghost',"
            " 'Signal', '{}', 'fk', 'queued', ?)", (db.now(),))
    conn.rollback()
    fks = {r[2] for r in conn.execute(
        "PRAGMA foreign_key_list(human_commands)")}
    assert fks == {"problems", "strategist_decisions"}
    conn.close()


def test_v49_migrated_human_commands_matches_a_fresh_one(
        tmp_path: Path) -> None:
    """Both directions of the completion condition: a v48-shaped
    `human_commands` migrated forward and a fresh `init_schema` one end
    at the same user_version, the same column shape and the same
    sqlite_master text."""
    fresh = sqlite3.connect(str(tmp_path / "fresh49.db"), timeout=30)
    fresh.row_factory = sqlite3.Row
    db.init_schema(fresh)
    old = sqlite3.connect(str(tmp_path / "old49.db"), timeout=30)
    old.row_factory = sqlite3.Row
    old.execute("PRAGMA foreign_keys = ON")
    db.init_schema(old)
    _rewind_to_v49_predecessor(old)
    db.init_schema(old)

    def shape(conn):
        return [(r[1], r[2], r[3], r[4], r[5])
                for r in conn.execute("PRAGMA table_info(human_commands)")]

    q = ("SELECT sql FROM sqlite_master WHERE type='table'"
         " AND name = 'human_commands'")
    assert shape(old) == shape(fresh)
    assert old.execute(q).fetchone()[0] == fresh.execute(q).fetchone()[0]
    assert (old.execute("PRAGMA user_version").fetchone()[0]
            == fresh.execute("PRAGMA user_version").fetchone()[0]
            == db._CURRENT_USER_VERSION == 54)
    old.close()
    fresh.close()


def test_the_ladder_restores_foreign_key_enforcement(tmp_path: Path) -> None:
    """A migrated connection must still ENFORCE its foreign keys.

    Every table rebuild disarms them (`_disarm_foreign_keys`) and re-arms
    in its own `finally` — but that re-arm runs inside the transaction
    the rebuild's `INSERT INTO _tmp SELECT *` opened, where `PRAGMA
    foreign_keys` is the same silent no-op the disarm was written to
    defeat. So the connection came out of the ladder unenforced, and
    `connect()` migrates: the daemon's own connection was the one it
    happened to. `PRAGMA foreign_key_check` cannot see this — it is a
    scan, not enforcement — so the probe here is a write that must be
    refused."""
    conn = sqlite3.connect(str(tmp_path / "fk.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    db.init_schema(conn)
    _rewind_to_v49_predecessor(conn)

    db.init_schema(conn)

    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO goals (problem, slug, lean_path, statement,"
            " origin, depth, status, created_at, updated_at) VALUES"
            " ('ghost', 's', 'p.lean', 'T', 'root', 0, 'open', ?, ?)",
            (db.now(), db.now()))
    conn.rollback()
    conn.close()


def test_the_ladder_leaves_an_unenforced_connection_unenforced(
        tmp_path: Path) -> None:
    """The restore is a RESTORE, not a policy: a caller that opened with
    foreign keys off (most test fixtures — `sqlite3.connect` defaults to
    off) gets its connection back the way it handed it over. Turning
    them on here would be this module deciding a caller's enforcement
    for it, one migration after the fact."""
    conn = sqlite3.connect(str(tmp_path / "nofk.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    db.init_schema(conn)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0
    conn.close()
