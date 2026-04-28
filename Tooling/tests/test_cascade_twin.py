"""P4 C30 integration tests for twin cascade + Refuter dispatch in scheduler.

Tests scheduler._cascade_twin_to_refuted (called from _update_goal_proved)
and scheduler._cascade_refuter (dispatched via _run_step3_cascade).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.scheduler import (
    FatalError,
    Reactor,
    ReactorConfig,
)
from Tooling.pipelines.refuter import RefuterResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def reactor(db, tmp_path):
    """Build a Reactor with conn already injected (bypasses startup)."""
    cfg = ReactorConfig(base_dir=str(tmp_path), pool_size=1)
    r = Reactor(str(tmp_path / "test.db"), cfg)
    r.conn = db
    return r


def _insert_goal(
    conn,
    *,
    problem: str = "P",
    slug: str = "g",
    lean_path: str | None = None,
    origin: str = "root",
    kind: str = "conjecture",
    status: str = "open",
    twin_of: int | None = None,
    answer_data: str | None = None,
) -> int:
    if lean_path is None:
        lean_path = f"Problems/{problem}/{slug}.lean"
    with conn:
        cur = conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "twin_of, answer_data, created_at, updated_at, depth) "
            "VALUES (?, ?, ?, ?, ?, ?, 'live', ?, ?, "
            "datetime('now'), datetime('now'), 0)",
            (problem, slug, lean_path, origin, kind, status,
             twin_of, answer_data),
        )
    return cur.lastrowid  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Twin cascade — basic
# ---------------------------------------------------------------------------

class TestTwinCascadeOnProve:
    """When a Goal becomes proved, its twin (if any) flips to refuted."""

    def test_g_proved_flips_negation_to_refuted(self, reactor):
        """Symmetric path: prove ¬G first, then twin G should refute."""
        conn = reactor.conn
        gid = _insert_goal(conn, slug="g")
        neg_id = _insert_goal(
            conn, slug="neg_g", origin="refuter_negation", kind="theorem",
            twin_of=gid,
        )
        # Bidirectional twin link
        with conn:
            conn.execute("UPDATE goals SET twin_of=? WHERE id=?", (neg_id, gid))

        ad = json.dumps({"type": "classical", "lean_path": f"Problems/P/neg_g.lean"})
        reactor._update_goal_proved(neg_id, ad, trust_set_json=None)

        # Twin G should now be refuted with classical type
        g_row = conn.execute(
            "SELECT status, answer_data FROM goals WHERE id = ?", (gid,)
        ).fetchone()
        assert g_row[0] == "refuted"
        ad_obj = json.loads(g_row[1])
        assert ad_obj["type"] == "classical"
        assert ad_obj["negation_goal_id"] == neg_id
        assert "neg_g.lean" in ad_obj["negation_lean_path"]

    def test_proved_goal_with_no_twin_no_refute(self, reactor):
        """Goal with twin_of=NULL should not trigger any twin cascade."""
        conn = reactor.conn
        gid = _insert_goal(conn, slug="solo")
        ad = json.dumps({"type": "classical", "lean_path": "Problems/P/solo.lean"})
        reactor._update_goal_proved(gid, ad, trust_set_json=None)
        # No other goal exists, no error
        rows = conn.execute(
            "SELECT count(*) FROM goals WHERE status='refuted'"
        ).fetchone()
        assert rows[0] == 0

    def test_refute_cascade_emits_event(self, reactor):
        conn = reactor.conn
        gid = _insert_goal(conn, slug="g_evt")
        neg_id = _insert_goal(
            conn, slug="neg_g_evt", origin="refuter_negation", kind="theorem",
            twin_of=gid,
        )
        with conn:
            conn.execute("UPDATE goals SET twin_of=? WHERE id=?", (neg_id, gid))

        ad = json.dumps({"type": "classical", "lean_path": "Problems/P/neg_g_evt.lean"})
        reactor._update_goal_proved(neg_id, ad, trust_set_json=None)

        events = conn.execute(
            "SELECT kind, payload FROM events WHERE kind='cascade'"
        ).fetchall()
        cascade_payloads = [json.loads(p) for _, p in events]
        # At least one twin cascade event with the right rule
        rule_hits = [e for e in cascade_payloads
                     if e.get("rule") == "twin_proved→refuted"]
        assert len(rule_hits) == 1
        assert rule_hits[0]["goal_id"] == gid
        assert rule_hits[0]["via_proved_goal_id"] == neg_id


# ---------------------------------------------------------------------------
# Dual-proved invariant violation
# ---------------------------------------------------------------------------

class TestDualProvedInvariantHalt:
    def test_real_dual_proved_triggers_fatal(self, reactor):
        """If twin already proved when proving its twin → fatal halt."""
        conn = reactor.conn
        gid = _insert_goal(conn, slug="dp_g", status="proved")
        neg_id = _insert_goal(
            conn, slug="dp_neg_g", origin="refuter_negation", kind="theorem",
            twin_of=gid, status="open",
        )
        with conn:
            conn.execute("UPDATE goals SET twin_of=? WHERE id=?", (neg_id, gid))

        ad = json.dumps({"type": "classical", "lean_path": "Problems/P/dp_neg_g.lean"})
        with pytest.raises(FatalError, match="dual_proved"):
            reactor._update_goal_proved(neg_id, ad, trust_set_json=None)

        # Fatal event recorded
        rows = conn.execute(
            "SELECT count(*) FROM events WHERE kind='fatal'"
        ).fetchone()
        assert rows[0] >= 1

    def test_cascade_fault_dual_proved_forces_fatal(self, reactor, monkeypatch):
        """CASCADE_FAULT=dual_proved forces fatal even when twin is not proved."""
        monkeypatch.setenv("CASCADE_FAULT", "dual_proved")
        conn = reactor.conn
        gid = _insert_goal(conn, slug="cf_g")
        neg_id = _insert_goal(
            conn, slug="cf_neg_g", origin="refuter_negation", kind="theorem",
            twin_of=gid,
        )
        with conn:
            conn.execute("UPDATE goals SET twin_of=? WHERE id=?", (neg_id, gid))

        ad = json.dumps({"type": "classical", "lean_path": "Problems/P/cf_neg_g.lean"})
        with pytest.raises(FatalError, match="dual_proved"):
            reactor._update_goal_proved(neg_id, ad, trust_set_json=None)

    def test_cascade_fault_other_modes_dont_fire_in_twin_path(
        self, reactor, monkeypatch
    ):
        """unique_violation / fk_invalid not yet wired to twin cascade —
        they don't fire here. Reserve names only for C30."""
        monkeypatch.setenv("CASCADE_FAULT", "unique_violation")
        conn = reactor.conn
        gid = _insert_goal(conn, slug="cf_uv_g")
        neg_id = _insert_goal(
            conn, slug="cf_uv_neg_g", origin="refuter_negation", kind="theorem",
            twin_of=gid,
        )
        with conn:
            conn.execute("UPDATE goals SET twin_of=? WHERE id=?", (neg_id, gid))

        ad = json.dumps({"type": "classical", "lean_path": "Problems/P/cf_uv.lean"})
        # No raise — unique_violation is reserve-name in C30
        reactor._update_goal_proved(neg_id, ad, trust_set_json=None)


class TestTwinDanglingPointer:
    """Dangling twin_of pointer is normally prevented by FK
    (`twin_of INTEGER REFERENCES goals(id)` with PRAGMA foreign_keys=ON).
    The cascade still has a defensive branch for robustness during DB
    recovery scenarios where FK might be temporarily off; this test
    exercises that branch by mutating the connection-level FK pragma.
    """

    def test_twin_pointer_to_missing_goal_emits_event(self, reactor):
        conn = reactor.conn
        # Temporarily disable FK to simulate a recovery scenario where
        # twin_of can point to a goal that no longer exists.
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            with conn:
                conn.execute(
                    "INSERT INTO goals "
                    "(problem, slug, lean_path, origin, kind, status, "
                    "commit_state, twin_of, depth, "
                    "created_at, updated_at) "
                    "VALUES (?, ?, ?, 'root', 'theorem', 'open', 'live', "
                    "999, 0, "
                    "datetime('now'), datetime('now'))",
                    ("P", "dangle_g", "Problems/P/dangle.lean"),
                )
            gid = conn.execute(
                "SELECT id FROM goals WHERE slug='dangle_g'"
            ).fetchone()[0]
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

        ad = json.dumps({"type": "classical", "lean_path": "Problems/P/dangle.lean"})
        # Should not raise
        reactor._update_goal_proved(gid, ad, trust_set_json=None)

        events = conn.execute(
            "SELECT payload FROM events WHERE kind='cascade'"
        ).fetchall()
        rules = [json.loads(p[0]).get("rule") for p in events]
        assert "twin_cascade_dangling_pointer" in rules


# ---------------------------------------------------------------------------
# Refuter cascade dispatch
# ---------------------------------------------------------------------------

class TestRefuterCascadeDispatch:
    def test_refuter_success_no_op(self, reactor):
        """Refuter success → no DB mutation by cascade (¬G inserted by Refuter
        itself; structural refill picks it up next cycle)."""
        conn = reactor.conn
        gid = _insert_goal(conn, slug="rs_g", kind="conjecture")

        result = RefuterResult(outcome="success", negation_goal_id=999)
        reactor._cascade_refuter(gid, result)

        # No dead_attempts row written for success path
        rows = conn.execute(
            "SELECT count(*) FROM dead_attempts WHERE pipeline_kind='Refuter'"
        ).fetchone()
        assert rows[0] == 0

    def test_refuter_exhausted_records_dead_attempt(self, reactor):
        conn = reactor.conn
        gid = _insert_goal(conn, slug="re_g", kind="conjecture")
        # A Refuter pipeline must exist for FK; insert one row
        with conn:
            conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "started_at) VALUES "
                "('pid_re', 'Refuter', 'atomic', ?, 'Goal', 'failed', "
                "datetime('now'))",
                (str(gid),),
            )

        result = RefuterResult(outcome="exhausted")
        reactor._cascade_refuter(gid, result)

        rows = conn.execute(
            "SELECT pipeline_kind, outcome, target_id FROM dead_attempts"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "Refuter"
        assert rows[0][1] == "exhausted"
        assert rows[0][2] == str(gid)

    def test_refuter_exhausted_no_pipeline_id_fatal(self, reactor):
        """Missing pipeline FK → FatalError per silent-failure red line."""
        conn = reactor.conn
        gid = _insert_goal(conn, slug="re_orphan", kind="conjecture")
        # No pipelines row inserted
        result = RefuterResult(outcome="exhausted")
        with pytest.raises(FatalError, match="refuter_failure_no_pipeline_id"):
            reactor._cascade_refuter(gid, result)

    def test_refuter_exhausted_archive_check_after_threshold(self, reactor):
        """5th Refuter exhausted → archive_check writes blocked_pipelines."""
        conn = reactor.conn
        gid = _insert_goal(conn, slug="rb_g", kind="conjecture")
        # Pre-populate 4 dead_attempts so this 5th call hits threshold
        with conn:
            conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "started_at) VALUES "
                "('pid_rb', 'Refuter', 'atomic', ?, 'Goal', 'failed', "
                "datetime('now'))",
                (str(gid),),
            )
            for i in range(4):
                conn.execute(
                    "INSERT INTO dead_attempts "
                    "(target_id, target_kind, pipeline_id, pipeline_kind, "
                    "outcome, reason_summary, ts) "
                    "VALUES (?, 'Goal', 'pid_rb', 'Refuter', 'exhausted', "
                    "?, datetime('now'))",
                    (str(gid), f"prior #{i}"),
                )

        result = RefuterResult(outcome="exhausted")
        reactor._cascade_refuter(gid, result)

        # blocked_pipelines should now contain 'Refuter'
        bp = conn.execute(
            "SELECT blocked_pipelines FROM goals WHERE id = ?", (gid,)
        ).fetchone()[0]
        assert bp is not None
        assert "Refuter" in bp


# ---------------------------------------------------------------------------
# step3 dispatch routing
# ---------------------------------------------------------------------------

class TestStep3DispatchRoutesRefuter:
    def test_refuter_kind_dispatches_via_table(self, reactor):
        """_run_step3_cascade with Refuter kind hits _cascade_refuter (not
        unknown_cascade_combination)."""
        conn = reactor.conn
        gid = _insert_goal(conn, slug="d_g", kind="conjecture")
        with conn:
            conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "started_at) VALUES "
                "('pid_d', 'Refuter', 'atomic', ?, 'Goal', 'failed', "
                "datetime('now'))",
                (str(gid),),
            )

        result = RefuterResult(outcome="exhausted")
        task = {"kind": "Refuter", "target_id": str(gid)}
        reactor._run_step3_cascade(task, result)

        # Should have written dead_attempts; should NOT have emitted
        # 'unknown_cascade_combination'
        events = conn.execute(
            "SELECT payload FROM events WHERE kind='cascade'"
        ).fetchall()
        rules = [json.loads(p[0]).get("rule") for p in events]
        assert "unknown_cascade_combination" not in rules
        # dead_attempts written
        cnt = conn.execute(
            "SELECT count(*) FROM dead_attempts WHERE pipeline_kind='Refuter'"
        ).fetchone()[0]
        assert cnt == 1
