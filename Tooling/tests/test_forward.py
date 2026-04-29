"""Tests for Tooling/pipelines/forward.py (P7 C52).

Boundary-mocked: agent + run_lean + dedupe.lean subprocess all stubbed.
Asserts pipeline outcomes + commit row shape.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.agent.provider import AgentResponse, FallbackChain
from Tooling.db.connect import connect, init_schema
from Tooling.lake import LakeResult
from Tooling.pipelines.forward import Forward, ForwardConfig


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
    monkeypatch.setenv("SEARCH_MOCK", "force_miss")


def _insert_goal(
    conn: sqlite3.Connection,
    *,
    problem: str = "p",
    slug: str = "g_seed",
    status: str = "proved",
    question: str = "True",
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


def _wrap_candidates(cands: list[dict]) -> str:
    return f"```json\n{json.dumps({'candidates': cands})}\n```"


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


def _make_forward(db, chain, base) -> Forward:
    return Forward(db, chain, ForwardConfig(
        base_dir=base, lake_cwd=base, max_retries=3,
    ))


# ---------------------------------------------------------------------------
# Force hooks
# ---------------------------------------------------------------------------


class TestForceHooks:
    def test_force_exhausted(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("FORWARD_FORCE", "exhausted")
        f = _make_forward(db, MagicMock(spec=FallbackChain), tmp_base)
        assert f.run(seed_goal_id=1).outcome == "exhausted"

    def test_force_no_novel(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("FORWARD_FORCE", "no_novel")
        f = _make_forward(db, MagicMock(spec=FallbackChain), tmp_base)
        assert f.run(seed_goal_id=1).outcome == "no_novel"

    def test_force_unknown_raises(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("FORWARD_FORCE", "bogus")
        f = _make_forward(db, MagicMock(spec=FallbackChain), tmp_base)
        with pytest.raises(ValueError, match="unknown FORWARD_FORCE"):
            f.run(seed_goal_id=1)


# ---------------------------------------------------------------------------
# Seed validation
# ---------------------------------------------------------------------------


class TestSeedValidation:
    def test_unknown_seed_returns_exhausted(self, db, tmp_base):
        f = _make_forward(db, MagicMock(spec=FallbackChain), tmp_base)
        assert f.run(seed_goal_id=999).outcome == "exhausted"

    def test_unproved_seed_returns_exhausted(self, db, tmp_base):
        gid = _insert_goal(db, status="open")
        f = _make_forward(db, MagicMock(spec=FallbackChain), tmp_base)
        assert f.run(seed_goal_id=gid).outcome == "exhausted"


# ---------------------------------------------------------------------------
# Parse candidates
# ---------------------------------------------------------------------------


class TestParse:
    def _parse(self, db, tmp_base, output):
        f = _make_forward(db, MagicMock(spec=FallbackChain), tmp_base)
        return f._parse_candidates(output)

    def test_valid_candidates(self, db, tmp_base):
        out = _wrap_candidates([
            {"slug": "g_corollary_1", "statement": "True", "reason": "..."},
        ])
        result = self._parse(db, tmp_base, out)
        assert result is not None
        assert len(result) == 1

    def test_no_json(self, db, tmp_base):
        assert self._parse(db, tmp_base, "no code block") is None

    def test_exhausted_outcome_returns_empty_list(self, db, tmp_base):
        out = '```json\n{"outcome": "exhausted", "candidates": []}\n```'
        assert self._parse(db, tmp_base, out) == []

    def test_missing_slug(self, db, tmp_base):
        out = _wrap_candidates([{"statement": "True"}])
        assert self._parse(db, tmp_base, out) is None

    def test_missing_statement(self, db, tmp_base):
        out = _wrap_candidates([{"slug": "x"}])
        assert self._parse(db, tmp_base, out) is None


# ---------------------------------------------------------------------------
# End-to-end run loop
# ---------------------------------------------------------------------------


class TestRunLoop:
    @patch("Tooling.pipelines.forward.run_lean")
    def test_success_writes_goal_row(self, mock_lake, db, tmp_base):
        mock_lake.return_value = LakeResult(
            outcome="proved",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        seed = _insert_goal(db, slug="g_seed", question="True")
        chain = _make_chain([_wrap_candidates([
            {"slug": "g_seed_corollary_1", "statement": "True", "reason": "x"},
        ])])
        f = _make_forward(db, chain, tmp_base)
        r = f.run(seed_goal_id=seed)
        assert r.outcome == "success"
        assert len(r.new_goal_ids) == 1
        rows = db.execute(
            "SELECT slug, origin, status FROM goals WHERE id = ?",
            (r.new_goal_ids[0],),
        ).fetchall()
        assert rows == [("g_seed_corollary_1", "forward", "open")]

    @patch("Tooling.pipelines.forward.run_lean")
    def test_self_verify_failure_triggers_retry(self, mock_lake, db, tmp_base):
        mock_lake.side_effect = [
            LakeResult(outcome="exhausted",
                       messages=[{"kind": "error", "data": "type mismatch"}]),
            LakeResult(outcome="proved",
                       messages=[{"kind": "hasSorry", "data": "uses sorry"}]),
        ]
        seed = _insert_goal(db, slug="g_seed", question="True")
        chain = _make_chain([
            _wrap_candidates([{"slug": "g_seed_c1", "statement": "True", "reason": "x"}]),
            _wrap_candidates([{"slug": "g_seed_c1", "statement": "True", "reason": "x"}]),
        ])
        f = _make_forward(db, chain, tmp_base)
        r = f.run(seed_goal_id=seed)
        assert r.outcome == "success"
        assert chain.run.call_count == 2

    @patch("Tooling.pipelines.forward.run_lean")
    def test_dedupe_drops_all_returns_no_novel(
        self, mock_lake, db, tmp_base, monkeypatch
    ):
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        # force_hit needs entries non-empty.
        seed = _insert_goal(db, slug="g_seed", question="True")
        mock_lake.return_value = LakeResult(
            outcome="proved",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        chain = _make_chain([_wrap_candidates([
            {"slug": "g_seed_c1", "statement": "True", "reason": "x"},
        ])])
        f = _make_forward(db, chain, tmp_base)
        r = f.run(seed_goal_id=seed)
        assert r.outcome == "no_novel"
        assert r.new_goal_ids == []

    @patch("Tooling.pipelines.forward.run_lean")
    def test_commit_two_candidates_no_unique_violation(
        self, mock_lake, db, tmp_base
    ):
        """R3 regression (audit_c52_c53_c54_c55.md HIGH-2): batch insert of
        2+ candidates used to write lean_path="" twice → UNIQUE constraint
        crash. Verify the UUID-qualified placeholder fix avoids it."""
        mock_lake.return_value = LakeResult(
            outcome="proved",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        seed = _insert_goal(db, slug="g_seed", question="True")
        chain = _make_chain([_wrap_candidates([
            {"slug": "g_seed_c1", "statement": "True", "reason": "..."},
            {"slug": "g_seed_c2", "statement": "True", "reason": "..."},
            {"slug": "g_seed_c3", "statement": "True", "reason": "..."},
        ])])
        f = _make_forward(db, chain, tmp_base)
        r = f.run(seed_goal_id=seed)
        assert r.outcome == "success"
        assert len(r.new_goal_ids) == 3
        # Each new goal should have a unique canonical lean_path.
        paths = db.execute(
            "SELECT lean_path FROM goals WHERE id IN (?, ?, ?)",
            tuple(r.new_goal_ids),
        ).fetchall()
        path_set = {p[0] for p in paths}
        assert len(path_set) == 3, f"lean_path collision: {path_set}"

    def test_no_response_then_max_retries_exhausted(self, db, tmp_base):
        seed = _insert_goal(db, slug="g_seed", question="True")
        chain = _make_chain([])  # always None
        f = _make_forward(db, chain, tmp_base)
        r = f.run(seed_goal_id=seed)
        assert r.outcome == "exhausted"
