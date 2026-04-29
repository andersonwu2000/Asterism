"""Tests for Tooling/pipelines/generalizer.py (P7 C53)."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from Tooling.agent.provider import AgentResponse, FallbackChain
from Tooling.db.connect import connect, init_schema
from Tooling.lake import LakeResult
from Tooling.pipelines.generalizer import Generalizer, GeneralizerConfig


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


@pytest.fixture(autouse=True)
def _stage_mocks(monkeypatch):
    monkeypatch.setenv("DEDUPE_MOCK", "force_miss")


def _insert_goal(
    conn: sqlite3.Connection,
    *, problem: str = "p", slug: str = "g_seed",
    status: str = "proved", question: str = "True",
) -> int:
    cur = conn.execute(
        "INSERT INTO goals "
        "(problem, slug, lean_path, origin, kind, status, commit_state, "
        "created_at, updated_at, question) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (problem, slug, f"Problems/{problem}/{slug}.lean",
         "root", "theorem", status, "live",
         _NOW.isoformat(), _NOW.isoformat(), question),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _wrap_success(slug: str, statement: str, reason: str = "x") -> str:
    return f"```json\n{json.dumps({
        'outcome': 'success',
        'candidate': {'slug': slug, 'statement': statement, 'reason': reason},
    })}\n```"


def _wrap_unproductive() -> str:
    return f"```json\n{json.dumps({'outcome': 'unproductive', 'reason': 'maxed'})}\n```"


def _make_chain(outputs: list[str]) -> FallbackChain:
    chain = MagicMock(spec=FallbackChain)
    iters = iter(outputs)

    def fake_run(model_tier=None, prompt=None, scope_dirs=None,
                 session_id=None, staging_dir=None):
        try:
            o = next(iters)
        except StopIteration:
            return (None, "no_response")
        return (AgentResponse(output=o, session_id=session_id or "s"), "success")

    chain.run.side_effect = fake_run
    return chain


def _make_gen(db, chain, base) -> Generalizer:
    return Generalizer(db, chain, GeneralizerConfig(
        base_dir=base, lake_cwd=base, max_retries=3,
    ))


# ---------------------------------------------------------------------------
# Force hooks
# ---------------------------------------------------------------------------

class TestForceHooks:
    @pytest.mark.parametrize("force", ["exhausted", "no_novel", "unproductive"])
    def test_force_outcomes(self, db, tmp_base, monkeypatch, force):
        monkeypatch.setenv("GENERALIZER_FORCE", force)
        g = _make_gen(db, MagicMock(spec=FallbackChain), tmp_base)
        assert g.run(source_goal_id=1).outcome == force

    def test_unknown_raises(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("GENERALIZER_FORCE", "bogus")
        g = _make_gen(db, MagicMock(spec=FallbackChain), tmp_base)
        with pytest.raises(ValueError, match="unknown GENERALIZER_FORCE"):
            g.run(source_goal_id=1)


# ---------------------------------------------------------------------------
# Seed validation
# ---------------------------------------------------------------------------

class TestSeedValidation:
    def test_unknown_seed(self, db, tmp_base):
        g = _make_gen(db, MagicMock(spec=FallbackChain), tmp_base)
        assert g.run(source_goal_id=999).outcome == "exhausted"

    def test_unproved_seed(self, db, tmp_base):
        gid = _insert_goal(db, status="open")
        g = _make_gen(db, MagicMock(spec=FallbackChain), tmp_base)
        assert g.run(source_goal_id=gid).outcome == "exhausted"


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

class TestParse:
    def _parse(self, db, tmp_base, output):
        g = _make_gen(db, MagicMock(spec=FallbackChain), tmp_base)
        return g._parse_response(output)

    def test_success_path(self, db, tmp_base):
        out = _wrap_success("g_general", "True")
        r = self._parse(db, tmp_base, out)
        assert r is not None and r["outcome"] == "success"

    def test_unproductive_path(self, db, tmp_base):
        r = self._parse(db, tmp_base, _wrap_unproductive())
        assert r == {"outcome": "unproductive"}

    def test_no_json(self, db, tmp_base):
        assert self._parse(db, tmp_base, "no code") is None

    def test_unknown_outcome(self, db, tmp_base):
        out = '```json\n{"outcome": "bogus"}\n```'
        assert self._parse(db, tmp_base, out) is None

    def test_missing_slug(self, db, tmp_base):
        out = '```json\n{"outcome": "success", "candidate": {"statement": "True"}}\n```'
        assert self._parse(db, tmp_base, out) is None


# ---------------------------------------------------------------------------
# End-to-end
# ---------------------------------------------------------------------------

class TestRunLoop:
    @patch("Tooling.pipelines.generalizer.run_lean")
    def test_success_writes_root_goal(self, mock_lake, db, tmp_base):
        mock_lake.return_value = LakeResult(
            outcome="proved",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        seed = _insert_goal(db, slug="g_seed", question="1 + 0 = 1")
        chain = _make_chain([
            _wrap_success("g_seed_general", "∀ n : Nat, n + 0 = n"),
        ])
        g = _make_gen(db, chain, tmp_base)
        r = g.run(source_goal_id=seed)
        assert r.outcome == "success"
        assert r.new_goal_id is not None
        rows = db.execute(
            "SELECT origin, status FROM goals WHERE id = ?",
            (r.new_goal_id,),
        ).fetchall()
        assert rows == [("generalizer", "open")]

    @patch("Tooling.pipelines.generalizer.run_lean")
    def test_unproductive_no_row_written(self, mock_lake, db, tmp_base):
        seed = _insert_goal(db, slug="g_seed", question="True")
        chain = _make_chain([_wrap_unproductive()])
        g = _make_gen(db, chain, tmp_base)
        before = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        r = g.run(source_goal_id=seed)
        after = db.execute("SELECT COUNT(*) FROM goals").fetchone()[0]
        assert r.outcome == "unproductive"
        assert before == after  # no new goal row

    @patch("Tooling.pipelines.generalizer.run_lean")
    def test_dedupe_hit_returns_no_novel(
        self, mock_lake, db, tmp_base, monkeypatch
    ):
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        mock_lake.return_value = LakeResult(
            outcome="proved",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        seed = _insert_goal(db, slug="g_seed", question="True")
        chain = _make_chain([_wrap_success("g_dup", "True")])
        g = _make_gen(db, chain, tmp_base)
        r = g.run(source_goal_id=seed)
        assert r.outcome == "no_novel"

    def test_no_response_exhausted(self, db, tmp_base):
        seed = _insert_goal(db, slug="g_seed", question="True")
        chain = _make_chain([])
        g = _make_gen(db, chain, tmp_base)
        assert g.run(source_goal_id=seed).outcome == "exhausted"


# ---------------------------------------------------------------------------
# failure_replay regression test (R3 fix audit_c52_c53_c54_c55.md HIGH-1)
# ---------------------------------------------------------------------------


class TestFailureReplay:
    """R3 regression: failure_replay used to query target_kind='forward' (a
    copy-paste from forward.py). It's now target_kind='Goal' + pipeline_kind
    discriminator so reflection actually surfaces past Generalizer attempts.
    """

    def _seed_dead_attempt(
        self, conn, *, target_id: int, pipeline_kind: str = "Generalizer",
        target_kind: str = "Goal",
    ) -> None:
        # Need a pipeline row first (FK).
        conn.execute(
            "INSERT INTO pipelines "
            "(id, kind, runtime, target_id, target_kind, status, started_at) "
            "VALUES (?, ?, 'atomic', ?, 'Goal', 'failed', ?)",
            (f"pipe-test-{target_id}-{pipeline_kind}", pipeline_kind,
             str(target_id), _NOW.isoformat()),
        )
        conn.execute(
            "INSERT INTO dead_attempts "
            "(target_id, target_kind, pipeline_id, pipeline_kind, "
            " outcome, reason_summary, ts) "
            "VALUES (?, ?, ?, ?, 'exhausted', ?, ?)",
            (str(target_id), target_kind,
             f"pipe-test-{target_id}-{pipeline_kind}",
             pipeline_kind, "g already maximal", _NOW.isoformat()),
        )
        conn.commit()

    def test_finds_generalizer_dead_attempts(self, db, tmp_base):
        seed = _insert_goal(db, slug="g_seed", question="True")
        self._seed_dead_attempt(db, target_id=seed)
        g = _make_gen(db, MagicMock(spec=FallbackChain), tmp_base)
        replay = g.failure_replay(source_goal_id=seed)
        assert len(replay) == 1
        assert "g already maximal" in replay[0]["reason_summary"]

    def test_filters_out_other_pipeline_kinds(self, db, tmp_base):
        seed = _insert_goal(db, slug="g_seed", question="True")
        # Forward dead_attempt on the same Goal — should NOT appear.
        self._seed_dead_attempt(
            db, target_id=seed, pipeline_kind="Forward",
            target_kind="forward",
        )
        # Generalizer dead_attempt — SHOULD appear.
        self._seed_dead_attempt(db, target_id=seed)
        g = _make_gen(db, MagicMock(spec=FallbackChain), tmp_base)
        replay = g.failure_replay(source_goal_id=seed)
        assert len(replay) == 1  # only Generalizer one
