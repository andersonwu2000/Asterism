-- Asterism DB schema v1
-- All 13 tables from architecture v3 §9.1.
-- Unused columns are nullable; no ALTER TABLE migration needed in future phases.
-- SQLite enums are enforced via CHECK constraints.
-- JSON columns are TEXT; timestamps are TEXT ISO8601.

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ──────────────────────────────────────────────────────────────
-- goals
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS goals (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    problem               TEXT    NOT NULL,
    slug                  TEXT    NOT NULL,
    lean_path             TEXT    NOT NULL UNIQUE,
    statement_hash        TEXT,
    origin                TEXT    NOT NULL
                              CHECK(origin IN (
                                  'root','backward','forward',
                                  'generalizer','refuter_negation','construction_witness'
                              )),
    kind                  TEXT    NOT NULL
                              CHECK(kind IN ('theorem','conjecture','construction')),
    question              TEXT,                          -- json nullable
    status                TEXT    NOT NULL
                              CHECK(status IN (
                                  'open','attempting','proved','refuted','shelved'
                              )),
    answer_data           TEXT,                          -- json nullable
    evidence              TEXT,                          -- json; app default {}
    twin_of               INTEGER REFERENCES goals(id),
    derived_from          INTEGER REFERENCES goals(id),
    blocked_pipelines     TEXT,                          -- json list; app default []
    depth                 INTEGER,
    commit_state          TEXT    NOT NULL
                              CHECK(commit_state IN ('pending','live')),
    prior_state_snapshot  TEXT,                          -- json nullable
    trust_set             TEXT,                          -- json nullable
    status_changed_at     TEXT,
    created_at            TEXT    NOT NULL,
    updated_at            TEXT    NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- strategies
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategies (
    id                           INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id                      INTEGER NOT NULL REFERENCES goals(id),
    lean_path                    TEXT    NOT NULL UNIQUE,
    status                       TEXT    NOT NULL
                                     CHECK(status IN (
                                         'proposed','in_progress','succeeded','dead'
                                     )),
    commit_state                 TEXT    NOT NULL
                                     CHECK(commit_state IN ('pending','live')),
    prior_state_snapshot         TEXT,                   -- json nullable
    parent_subgoal_max_similarity REAL,
    created_by                   TEXT    REFERENCES pipelines(id),
    created_at                   TEXT    NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- strategy_subgoals  (M:N junction)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategy_subgoals (
    strategy_id  INTEGER NOT NULL REFERENCES strategies(id),
    subgoal_id   INTEGER NOT NULL REFERENCES goals(id),
    position     INTEGER NOT NULL,
    PRIMARY KEY (strategy_id, subgoal_id)
);

-- ──────────────────────────────────────────────────────────────
-- pipelines  (active + history)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipelines (
    id           TEXT PRIMARY KEY,                       -- UUID
    kind         TEXT NOT NULL
                     CHECK(kind IN (
                         'Builder','Backward','Refuter','Forward',
                         'Generalizer','Counterexample','ConstructionSearch','Strategist'
                     )),
    runtime      TEXT NOT NULL
                     CHECK(runtime IN ('atomic','continuous')),
    target_id    TEXT NOT NULL,
    target_kind  TEXT NOT NULL
                     CHECK(target_kind IN ('Goal','Strategy','forward')),
    status       TEXT NOT NULL
                     CHECK(status IN ('running','succeeded','failed')),
    outcome      TEXT,
    session_id   TEXT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);

-- ──────────────────────────────────────────────────────────────
-- dead_attempts  (failure_replay source)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dead_attempts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id      TEXT    NOT NULL,
    target_kind    TEXT    NOT NULL
                       CHECK(target_kind IN ('Goal','Strategy','forward')),
    pipeline_id    TEXT    REFERENCES pipelines(id),
    pipeline_kind  TEXT    NOT NULL
                       CHECK(pipeline_kind IN (
                           'Builder','Backward','Refuter','Forward',
                           'Generalizer','Counterexample','ConstructionSearch','Strategist'
                       )),
    outcome        TEXT    NOT NULL,
    reason_summary TEXT    NOT NULL,
    ts             TEXT    NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- queue  (pending tasks for scheduler)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT    NOT NULL
                    CHECK(kind IN (
                        'Builder','Backward','Refuter','Forward',
                        'Generalizer','Counterexample','ConstructionSearch','Strategist'
                    )),
    target_id   TEXT    NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 0,
    payload     TEXT,                                    -- json
    created_at  TEXT    NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- events  (audit log)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    kind     TEXT    NOT NULL
                 CHECK(kind IN (
                     'pipeline_finished','task_checkpoint','control_signal',
                     'cascade','evidence_updated','fatal'
                 )),
    payload  TEXT,                                       -- json
    ts       TEXT    NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- schedulers  (liveness; replaces .scheduler.lock)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schedulers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    host            TEXT    NOT NULL,
    pid             INTEGER NOT NULL,
    started_at      TEXT    NOT NULL,
    last_heartbeat  TEXT    NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- continuous_tasks  (P5+; schema present, runtime not consumed in P1)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS continuous_tasks (
    pipeline_id              TEXT    PRIMARY KEY REFERENCES pipelines(id),
    checkpoint_state         TEXT,                       -- json
    last_checkpoint_at       TEXT,
    budget_tokens            INTEGER,
    budget_wall_clock_sec    INTEGER,
    consumed_tokens          INTEGER NOT NULL DEFAULT 0,
    consumed_wall_clock_sec  INTEGER NOT NULL DEFAULT 0,
    lifecycle_state          TEXT    NOT NULL
                                 CHECK(lifecycle_state IN (
                                     'running','paused','done','killed'
                                 ))
);

-- ──────────────────────────────────────────────────────────────
-- construction_attempts  (P5+; schema present, runtime not consumed in P1)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS construction_attempts (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id          TEXT    NOT NULL REFERENCES pipelines(id),
    generation           INTEGER NOT NULL,
    parent_attempt_id    INTEGER REFERENCES construction_attempts(id),
    candidate_lean_path  TEXT    NOT NULL,
    score                REAL    NOT NULL,
    created_at           TEXT    NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- library_index  (P6+; schema present, runtime not consumed in P1)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS library_index (
    layer          TEXT NOT NULL
                       CHECK(layer IN ('Theorems','Counterexamples','Constructions')),
    name           TEXT NOT NULL,
    path           TEXT NOT NULL,
    source_root_id INTEGER REFERENCES goals(id),
    committed_at   TEXT NOT NULL,
    PRIMARY KEY (layer, name)
);

-- ──────────────────────────────────────────────────────────────
-- search_cache  (P3+; schema present, runtime not consumed in P1)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS search_cache (
    query_hash  TEXT PRIMARY KEY,
    scope       TEXT NOT NULL,
    mode        TEXT NOT NULL,
    results     TEXT NOT NULL,                           -- json
    expires_at  TEXT NOT NULL
);

-- ──────────────────────────────────────────────────────────────
-- strategist_decisions  (P7+; schema present, runtime not consumed in P1)
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS strategist_decisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    decisions  TEXT NOT NULL,                            -- json
    ts         TEXT NOT NULL
);
