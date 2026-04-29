"""Tests for Tooling/pipelines/strategist.py (P7 C50).

Strategy:
  - mock the FallbackChain at the boundary; do NOT touch real claude CLI.
  - assert: prompt template substitutions, JSON parse / retry semantics,
    decisions row written, demux invoked.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from Tooling.agent.provider import AgentResponse, FallbackChain
from Tooling.db.connect import connect, init_schema
from Tooling.pipelines.strategist import (
    Strategist,
    StrategistConfig,
    StrategistResult,
)


_NOW = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    conn = connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def tmp_base():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _insert_goal(
    conn: sqlite3.Connection,
    *,
    problem: str = "p",
    slug: str = "g",
    status: str = "open",
) -> int:
    cur = conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, commit_state, "
        "created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"Problems/{problem}/{slug}.lean",
         "root", "theorem", status, "live",
         _NOW.isoformat(), _NOW.isoformat()),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _make_chain(response_outputs: list[str]) -> FallbackChain:
    """Return a FallbackChain mock that yields outputs in order then None."""
    chain = MagicMock(spec=FallbackChain)
    iters = iter(response_outputs)

    def fake_run(model_tier=None, prompt=None, scope_dirs=None,
                 session_id=None, staging_dir=None):
        try:
            output = next(iters)
        except StopIteration:
            return (None, "no_response")
        return (AgentResponse(output=output, session_id=session_id or "s"),
                "success")

    chain.run.side_effect = fake_run
    return chain


def _make_strategist(db, chain, base) -> Strategist:
    config = StrategistConfig(base_dir=base, max_retries=3, max_decisions=5)
    return Strategist(db, chain, config)


def _wrap_decisions(decisions: list[dict], reasoning: str = "test") -> str:
    """Wrap a decisions list in the agent JSON output format."""
    return f"```json\n{json.dumps({'reasoning': reasoning, 'decisions': decisions})}\n```"


# ---------------------------------------------------------------------------
# Hooks
# ---------------------------------------------------------------------------

class TestForceHooks:
    def test_force_exhausted(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("STRATEGIST_FORCE", "exhausted")
        s = _make_strategist(db, MagicMock(spec=FallbackChain), tmp_base)
        r = s.run("p")
        assert r.outcome == "exhausted"
        assert r.decisions_id is None

    def test_force_empty(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("STRATEGIST_FORCE", "empty")
        s = _make_strategist(db, MagicMock(spec=FallbackChain), tmp_base)
        r = s.run("p")
        assert r.outcome == "success"
        assert r.raw_decisions == []
        assert r.decisions_id is not None
        # Row exists in strategist_decisions.
        rows = db.execute(
            "SELECT decisions FROM strategist_decisions WHERE id = ?",
            (r.decisions_id,),
        ).fetchall()
        assert rows == [("[]",)]

    def test_force_unknown_raises(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("STRATEGIST_FORCE", "bogus")
        s = _make_strategist(db, MagicMock(spec=FallbackChain), tmp_base)
        with pytest.raises(ValueError, match="unknown STRATEGIST_FORCE"):
            s.run("p")


# ---------------------------------------------------------------------------
# self_verify (JSON schema)
# ---------------------------------------------------------------------------

class TestParseResponse:
    def _parse(self, db, tmp_base, output: str):
        s = _make_strategist(db, MagicMock(spec=FallbackChain), tmp_base)
        return s._parse_response(output)

    def test_valid_decisions(self, db, tmp_base):
        out = _wrap_decisions([
            {"kind": "Backward", "target": 1, "reason": "..."},
        ])
        parsed = self._parse(db, tmp_base, out)
        assert parsed is not None
        assert parsed["decisions"][0]["kind"] == "Backward"

    def test_no_json_block(self, db, tmp_base):
        assert self._parse(db, tmp_base, "no json here") is None

    def test_decisions_not_list(self, db, tmp_base):
        out = '```json\n{"reasoning": "x", "decisions": {}}\n```'
        assert self._parse(db, tmp_base, out) is None

    def test_unknown_kind(self, db, tmp_base):
        out = _wrap_decisions(
            [{"kind": "Bogus", "target": 1, "reason": "..."}]
        )
        assert self._parse(db, tmp_base, out) is None

    def test_target_not_int(self, db, tmp_base):
        out = _wrap_decisions(
            [{"kind": "Backward", "target": "G_1", "reason": "..."}]
        )
        assert self._parse(db, tmp_base, out) is None

    def test_missing_reason(self, db, tmp_base):
        out = _wrap_decisions([{"kind": "Backward", "target": 1}])
        assert self._parse(db, tmp_base, out) is None

    def test_too_many_decisions(self, db, tmp_base):
        decisions = [
            {"kind": "Backward", "target": i, "reason": "..."}
            for i in range(6)  # > max_decisions=5
        ]
        out = _wrap_decisions(decisions)
        assert self._parse(db, tmp_base, out) is None


# ---------------------------------------------------------------------------
# Run loop: agent retry on bad schema
# ---------------------------------------------------------------------------

class TestRunLoop:
    def test_agent_retry_on_bad_schema(self, db, tmp_base):
        gid = _insert_goal(db, problem="p", slug="g_root")
        good = _wrap_decisions(
            [{"kind": "Backward", "target": gid, "reason": "ok"}]
        )
        chain = _make_chain(["no json here", good])
        s = _make_strategist(db, chain, tmp_base)
        r = s.run("p")
        assert r.outcome == "success"
        # Two agent calls: one bad, one good.
        assert chain.run.call_count == 2

    def test_exhausted_after_max_retries(self, db, tmp_base):
        chain = _make_chain(["bad"] * 5)
        s = _make_strategist(db, chain, tmp_base)
        r = s.run("p")
        assert r.outcome == "exhausted"
        assert chain.run.call_count == 3  # max_retries

    def test_decisions_row_written_on_success(self, db, tmp_base):
        gid = _insert_goal(db, problem="p", slug="g_root")
        chain = _make_chain([_wrap_decisions(
            [{"kind": "Backward", "target": gid, "reason": "x"}]
        )])
        s = _make_strategist(db, chain, tmp_base)
        r = s.run("p")
        assert r.outcome == "success"
        rows = db.execute(
            "SELECT decisions FROM strategist_decisions WHERE id = ?",
            (r.decisions_id,),
        ).fetchall()
        decisions = json.loads(rows[0][0])
        assert decisions == [{"kind": "Backward", "target": gid, "reason": "x"}]

    def test_demux_runs_after_commit(self, db, tmp_base):
        gid = _insert_goal(db, problem="p", slug="g_root")
        chain = _make_chain([_wrap_decisions(
            [{"kind": "Backward", "target": gid, "reason": "x"}]
        )])
        s = _make_strategist(db, chain, tmp_base)
        r = s.run("p")
        assert r.demux is not None
        assert len(r.demux.enqueued) == 1
        # Queue row exists.
        q = db.execute("SELECT kind, target_id FROM queue").fetchall()
        assert q == [("Backward", str(gid))]


# ---------------------------------------------------------------------------
# Pipeline lifecycle
# ---------------------------------------------------------------------------

class TestPipelineRow:
    def test_pipeline_inserted_with_problem_marker(self, db, tmp_base):
        gid = _insert_goal(db, problem="p", slug="g_root")
        chain = _make_chain([_wrap_decisions(
            [{"kind": "Backward", "target": gid, "reason": "x"}]
        )])
        s = _make_strategist(db, chain, tmp_base)
        s.run("p")
        rows = db.execute(
            "SELECT kind, target_id, status, outcome FROM pipelines"
        ).fetchall()
        # Strategist row + Backward injection row not yet (queue, not pipelines)
        kinds = [r[0] for r in rows]
        assert "Strategist" in kinds
        s_row = next(r for r in rows if r[0] == "Strategist")
        assert s_row[1] == "_problem:p"
        assert s_row[2] == "succeeded"
        assert s_row[3] == "success"


# ---------------------------------------------------------------------------
# failure_replay (decisions × pipelines join)
# ---------------------------------------------------------------------------

class TestFailureReplay:
    def test_returns_recent_decisions_with_outcomes(self, db, tmp_base):
        gid = _insert_goal(db, problem="p", slug="g")
        # Pre-seed a strategist_decisions row + matching pipeline row.
        decisions = [
            {"kind": "Backward", "target": gid, "reason": "earlier try"},
        ]
        ts = _NOW.isoformat()
        db.execute(
            "INSERT INTO strategist_decisions (decisions, ts) VALUES (?, ?)",
            (json.dumps(decisions), ts),
        )
        db.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, outcome, "
            "started_at) VALUES (?, 'Backward', 'atomic', ?, 'Goal', "
            "'failed', 'exhausted', ?)",
            ("p1", str(gid), ts),
        )
        db.commit()

        s = _make_strategist(db, MagicMock(spec=FallbackChain), tmp_base)
        replay = s.failure_replay()
        assert len(replay) == 1
        assert replay[0]["joined"] == [
            {
                "decision": decisions[0],
                "outcome": "exhausted",
            }
        ]
