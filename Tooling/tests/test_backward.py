"""Unit tests for Tooling/pipelines/backward.py (C13)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.commit import CommitFault
from Tooling.db.connect import connect, init_schema
from Tooling.lake import LakeResult
from Tooling.agent.provider import AgentResponse, FallbackChain
from Tooling.pipelines.backward import Backward, BackwardConfig, BackwardResult


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    conn = connect(":memory:")
    init_schema(conn)
    return conn


@pytest.fixture
def tmp_base(tmp_path):
    return str(tmp_path)


@pytest.fixture(autouse=True)
def _stage_mocks(monkeypatch):
    """C22/C23: Backward.run now invokes real subsystem stages via subprocess
    (dedupe.lean + search.lean). Most test_backward.py tests don't care about
    those details and would time out without lake env — force-miss both so
    every candidate counts as novel and search returns []. Per-test
    overrides allowed inside the test body via monkeypatch.setenv.
    """
    monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
    monkeypatch.setenv("SEARCH_MOCK", "force_miss")


def _insert_goal(
    conn,
    problem: str = "test",
    slug: str = "G_root",
    lean_path: str | None = None,
    depth: int = 0,
    question: str = "True",
) -> int:
    if lean_path is None:
        lean_path = f"Problems/{problem}/{slug}.lean"
    with conn:
        cur = conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at, depth, question) "
            "VALUES (?, ?, ?, 'root', 'theorem', 'open', 'live', "
            "datetime('now'), datetime('now'), ?, ?)",
            (problem, slug, lean_path, depth, question),
        )
    return cur.lastrowid  # type: ignore[return-value]


def _make_backward(
    db,
    chain: FallbackChain | None = None,
    base_dir: str | None = None,
    lake_cwd: str = ".",
    max_retries: int = 3,
) -> Backward:
    if chain is None:
        chain = MagicMock(spec=FallbackChain)
    if base_dir is None:
        base_dir = tempfile.mkdtemp()
    config = BackwardConfig(base_dir=base_dir, lake_cwd=lake_cwd, max_retries=max_retries)
    return Backward(db, chain, config)


def _make_response(proposal: dict, session_id: str = "s1") -> AgentResponse:
    return AgentResponse(
        output=f"```json\n{json.dumps(proposal)}\n```",
        session_id=session_id,
    )


def _simple_proposal(parent_slug: str = "G_root", n: int = 2) -> dict:
    return {
        "combinator": "And",
        "subgoals": [
            {"slug": f"{parent_slug}_sub_{i+1}", "statement": f"True -- sub {i+1}"}
            for i in range(n)
        ],
        "leaf_claims": [],
    }


# ---------------------------------------------------------------------------
# Stub stages
# ---------------------------------------------------------------------------

class TestStageDelegation:
    """C22 wired three Backward stages to Tooling.stages modules.

    Empty-database / empty-search baselines:
      - failure_replay: no dead_attempts rows → []
      - find_lemmas:    SEARCH_MOCK=force_miss → []
      - find_subgoals:  no live goals match query → []
    """
    def test_failure_replay_no_dead_attempts(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        assert bw.failure_replay(goal_id=1) == []

    def test_find_lemmas_with_search_mock(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("SEARCH_MOCK", "force_miss")
        bw = _make_backward(db, base_dir=tmp_base)
        assert bw.find_lemmas({"problem": "test", "slug": "g"}) == []

    def test_find_subgoals_empty_goals_table(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        assert bw.find_subgoals({"problem": "test", "slug": "g"}) == []


# ---------------------------------------------------------------------------
# Parse PROPOSAL
# ---------------------------------------------------------------------------

class TestParseProposal:
    def test_json_code_block(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        proposal = {"combinator": "And", "subgoals": [], "leaf_claims": []}
        out = f"```json\n{json.dumps(proposal)}\n```"
        result = bw._parse_proposal(out)
        assert result is not None
        assert result["combinator"] == "And"

    def test_bare_code_block(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        proposal = {"combinator": "Or", "subgoals": [], "leaf_claims": []}
        out = f"```\n{json.dumps(proposal)}\n```"
        result = bw._parse_proposal(out)
        assert result is not None
        assert result["combinator"] == "Or"

    def test_no_json_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        assert bw._parse_proposal("no json here at all") is None

    def test_malformed_json_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        assert bw._parse_proposal("```json\n{broken: true\n```") is None

    def test_missing_combinator_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        out = '```json\n{"subgoals": []}\n```'
        assert bw._parse_proposal(out) is None

    def test_invalid_combinator_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        proposal = {"combinator": "Misc", "subgoals": [], "leaf_claims": []}
        out = f"```json\n{json.dumps(proposal)}\n```"
        assert bw._parse_proposal(out) is None

    def test_subgoals_not_list_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        out = '```json\n{"combinator": "And", "subgoals": "oops"}\n```'
        assert bw._parse_proposal(out) is None

    def test_subgoal_missing_slug_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        proposal = {
            "combinator": "And",
            "subgoals": [{"statement": "True"}],
            "leaf_claims": [],
        }
        out = f"```json\n{json.dumps(proposal)}\n```"
        assert bw._parse_proposal(out) is None

    def test_subgoal_missing_statement_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        proposal = {
            "combinator": "And",
            "subgoals": [{"slug": "s1"}],
            "leaf_claims": [],
        }
        out = f"```json\n{json.dumps(proposal)}\n```"
        assert bw._parse_proposal(out) is None

    def test_subgoal_empty_slug_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        proposal = {
            "combinator": "And",
            "subgoals": [{"slug": "", "statement": "True"}],
            "leaf_claims": [],
        }
        out = f"```json\n{json.dumps(proposal)}\n```"
        assert bw._parse_proposal(out) is None

    def test_top_level_not_dict_returns_none(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        out = '```json\n["combinator", "And"]\n```'
        assert bw._parse_proposal(out) is None


# ---------------------------------------------------------------------------
# Normalize hash / dedupe
# ---------------------------------------------------------------------------

# C23 removed Backward._normalize_hash (P2 statement_hash 完全取代 by dedupe.lean).
# Equivalent isDefEq behavior is tested in test_dedupe.py + test_backward.py::TestDedupe.


class TestDedupe:
    """C23: dedupe.lean (Lean.Meta.isDefEq) replaces P2 statement_hash.

    Subprocess is mocked via DEDUPE_MOCK env hook (force_hit / force_miss);
    these tests assert the wrapper behavior in Backward._dedupe — within-
    proposal text-equal short-circuit, subprocess call count, slug
    preservation. Real isDefEq behavior is tested in test_dedupe.py.
    """

    def test_force_miss_keeps_all_unique(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
        bw = _make_backward(db, base_dir=tmp_base)
        subgoals = [{"slug": "sub1", "statement": "1 + 1 = 2"}]
        result = bw._dedupe(subgoals, str(tmp_base), {"problem": "test"})
        assert len(result) == 1
        assert result[0]["slug"] == "sub1"
        # statement_hash no longer populated (C23 完全取代)
        assert "statement_hash" not in result[0] or result[0].get("statement_hash") is None

    def test_force_hit_filters_all(self, db, tmp_base, monkeypatch):
        """When dedupe.lean reports hit for every candidate, all are filtered."""
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        # force_hit needs entries non-empty; insert a placeholder live goal.
        _insert_goal(db, slug="seed_goal")
        bw = _make_backward(db, base_dir=tmp_base)
        subgoals = [{"slug": "sub1", "statement": "1 + 1 = 2"}]
        result = bw._dedupe(subgoals, str(tmp_base), {"problem": "test"})
        assert result == []

    def test_intra_proposal_text_dedup(self, db, tmp_base, monkeypatch):
        """Same-text sub-goals in one proposal collapse before subprocess
        is even called (within-proposal cheap text-equal check)."""
        monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
        bw = _make_backward(db, base_dir=tmp_base)
        subgoals = [
            {"slug": "sub1", "statement": "1 + 1 = 2"},
            {"slug": "sub2", "statement": "1 + 1 = 2"},  # duplicate text
            {"slug": "sub3", "statement": "2 + 2 = 4"},
        ]
        result = bw._dedupe(subgoals, str(tmp_base), {"problem": "test"})
        assert len(result) == 2
        assert {sg["slug"] for sg in result} == {"sub1", "sub3"}

    def test_no_statement_hash_in_output(self, db, tmp_base, monkeypatch):
        """C23 spec: 完全取代 P2 statement_hash code — column NULL for new sub-goals."""
        monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
        bw = _make_backward(db, base_dir=tmp_base)
        result = bw._dedupe(
            [{"slug": "sub1", "statement": "True"}], str(tmp_base),
            {"problem": "test"},
        )
        assert result[0].get("statement_hash") is None or "statement_hash" not in result[0]

    def test_subprocess_runtime_error_propagates(self, db, tmp_base, monkeypatch):
        """C23 R3 LOW-1: subprocess RuntimeError must propagate to caller
        (not silently fall through to NOVEL). Pin the wrapper-level invariant
        so future refactors can't slip silent-failure pattern back in."""
        monkeypatch.delenv("DEDUPE_MOCK", raising=False)
        _insert_goal(db, slug="seed")
        bw = _make_backward(db, base_dir=tmp_base)
        with patch(
            "Tooling.pipelines.backward._stage_dedupe",
            side_effect=RuntimeError("dedupe.lean rc=1, no JSON"),
        ):
            with pytest.raises(RuntimeError, match="dedupe.lean rc=1"):
                bw._dedupe(
                    [{"slug": "sub1", "statement": "True"}],
                    str(tmp_base),
                    {"problem": "test"},
                )

    def test_entries_scoped_to_parent_problem(self, db, tmp_base, monkeypatch):
        """C23 R3 MED-2: dedupe entries SELECT must filter by parent's
        problem so cross-Problem α-equiv goals don't silently drop sub-goals."""
        from unittest.mock import MagicMock
        monkeypatch.delenv("DEDUPE_MOCK", raising=False)
        _insert_goal(db, slug="A_entry", problem="A",
                     lean_path="Problems/A/A_entry.lean")
        _insert_goal(db, slug="B_entry", problem="B",
                     lean_path="Problems/B/B_entry.lean")

        captured: list[list[dict]] = []
        def fake_dedupe(cand_path, entries, **kwargs):
            from Tooling.subsystems.dedupe import DedupeResult
            captured.append(list(entries))
            return DedupeResult(outcome="novel")

        bw = _make_backward(db, base_dir=tmp_base)
        with patch("Tooling.pipelines.backward._stage_dedupe",
                   side_effect=fake_dedupe):
            bw._dedupe(
                [{"slug": "sub1", "statement": "True"}],
                str(tmp_base),
                {"problem": "A"},
            )
        # entries passed to dedupe should only include Problem A's row
        assert len(captured) == 1
        slugs_in_paths = [e["lean_path"] for e in captured[0]]
        assert any("/A/" in p for p in slugs_in_paths)
        assert not any("/B/" in p for p in slugs_in_paths)


# ---------------------------------------------------------------------------
# Agent stage
# ---------------------------------------------------------------------------

class TestAgentStage:
    def test_exhausted_chain_returns_exhausted(self, db, tmp_base):
        chain = MagicMock(spec=FallbackChain)
        chain.run.return_value = (None, "exhausted")
        bw = _make_backward(db, chain=chain, base_dir=tmp_base, max_retries=2)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)
        assert result.outcome == "exhausted"

    def test_unproductive_empty_subgoals(self, db, tmp_base):
        chain = MagicMock(spec=FallbackChain)
        proposal = {"combinator": "And", "subgoals": [], "leaf_claims": []}
        chain.run.return_value = (_make_response(proposal), "success")
        bw = _make_backward(db, chain=chain, base_dir=tmp_base)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)
        assert result.outcome == "unproductive"

    def test_unproductive_all_dupes(self, db, tmp_base, monkeypatch):
        """C23: when dedupe.lean reports every sub-goal is a hit (duplicate),
        Backward returns unproductive."""
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        # force_hit needs entries non-empty
        _insert_goal(db, slug="seed_for_dedupe")
        chain = MagicMock(spec=FallbackChain)
        proposal = {
            "combinator": "And",
            "subgoals": [{"slug": "sub1", "statement": "True"}],
            "leaf_claims": [],
        }
        chain.run.return_value = (_make_response(proposal), "success")
        bw = _make_backward(db, chain=chain, base_dir=tmp_base)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)
        assert result.outcome == "unproductive"

    def test_null_parse_retries(self, db, tmp_base):
        chain = MagicMock(spec=FallbackChain)
        # All responses produce unparseable output
        chain.run.return_value = (
            AgentResponse(output="no json here", session_id="s1"),
            "success",
        )
        bw = _make_backward(db, chain=chain, base_dir=tmp_base, max_retries=3)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)
        assert result.outcome == "exhausted"
        assert chain.run.call_count == 3

    def test_goal_not_found_returns_exhausted(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        result = bw.run(99999)
        assert result.outcome == "exhausted"


# ---------------------------------------------------------------------------
# Validator retry
# ---------------------------------------------------------------------------

class TestValidatorRetry:
    def test_validator_reject_retries_up_to_max(self, db, tmp_base):
        chain = MagicMock(spec=FallbackChain)
        # Proposal exceeds MAX_SUBGOALS=8 → validator rejects every time
        proposal = {
            "combinator": "And",
            "subgoals": [
                {"slug": f"G_root_sub_{i}", "statement": f"True -- {i}"}
                for i in range(9)  # 9 > MAX_SUBGOALS=8
            ],
            "leaf_claims": [],
        }
        chain.run.return_value = (_make_response(proposal), "success")

        bw = _make_backward(db, chain=chain, base_dir=tmp_base, max_retries=2)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)

        assert result.outcome == "exhausted"
        assert chain.run.call_count == 2

    @patch("Tooling.pipelines.backward.validate")
    @patch("Tooling.pipelines.backward.run_lean")
    def test_validator_pass_then_commit(self, mock_lake, mock_validate, db, tmp_path):
        mock_validate.return_value = []
        mock_lake.return_value = LakeResult(outcome="exhausted")

        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal()
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))

        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path), max_retries=3)
        bw = Backward(db, chain, config)
        result = bw.run(goal_id)

        assert result.outcome == "success"
        assert chain.run.call_count == 1


# ---------------------------------------------------------------------------
# Self-verify retry on lake failure (audit #2)
# ---------------------------------------------------------------------------


class TestSelfVerifyRetry:
    """`_self_verify_per_file` returns (all_pass, augmented). Failure must
    drive a retry from the agent stage (pipelines.md §2 stage 7 fail path)."""

    def _setup(self, db, tmp_path):
        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=2)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(
            base_dir=str(tmp_path), lake_cwd=str(tmp_path), max_retries=2
        )
        return Backward(db, chain, config), goal_id, chain

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_lake_elab_error_triggers_retry(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        # All retries see elab error → retry max_retries times → exhausted.
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "error", "data": "type mismatch"}],
        )
        bw, goal_id, chain = self._setup(db, tmp_path)
        result = bw.run(goal_id)
        assert result.outcome == "exhausted"
        assert chain.run.call_count == 2

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_lake_timeout_triggers_retry(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        mock_lake.return_value = LakeResult(outcome="exhausted", timed_out=True)
        bw, goal_id, chain = self._setup(db, tmp_path)
        result = bw.run(goal_id)
        assert result.outcome == "exhausted"
        assert chain.run.call_count == 2

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_hassorry_only_passes(self, mock_lake, mock_validate, db, tmp_path):
        # Sorry-stub case: outcome=exhausted but only message is hasSorry → PASS.
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        bw, goal_id, chain = self._setup(db, tmp_path)
        result = bw.run(goal_id)
        assert result.outcome == "success"
        assert chain.run.call_count == 1

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_mixed_messages_with_non_sorry_fails(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        """Even a hasSorry alongside an error counts as fail."""
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[
                {"kind": "hasSorry", "data": "uses sorry"},
                {"kind": "error", "data": "unknown ident"},
            ],
        )
        bw, goal_id, chain = self._setup(db, tmp_path)
        result = bw.run(goal_id)
        assert result.outcome == "exhausted"
        assert chain.run.call_count == 2


# ---------------------------------------------------------------------------
# Commit batch atomicity
# ---------------------------------------------------------------------------

class TestCommitBatch:
    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_commit_creates_strategy_and_subgoals(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        mock_lake.return_value = LakeResult(outcome="exhausted")

        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=2)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        bw = Backward(db, chain, config)
        result = bw.run(goal_id)

        assert result.outcome == "success"
        assert result.strategy_id is not None
        assert len(result.subgoal_ids) == 2

        # strategy in DB, commit_state='live', status='proposed'
        strat_row = db.execute(
            "SELECT status, commit_state, goal_id FROM strategies WHERE id = ?",
            (result.strategy_id,),
        ).fetchone()
        assert strat_row is not None
        assert strat_row[0] == "proposed"
        assert strat_row[1] == "live"
        assert strat_row[2] == goal_id

        # subgoal goals in DB, commit_state='live'
        sg_rows = db.execute(
            f"SELECT id, status, commit_state, origin, kind, depth FROM goals "
            f"WHERE id IN ({','.join('?' * len(result.subgoal_ids))})",
            result.subgoal_ids,
        ).fetchall()
        assert len(sg_rows) == 2
        for row in sg_rows:
            assert row[2] == "live"
            assert row[3] == "backward"
            assert row[4] == "theorem"
            assert row[5] == 1  # depth = parent(0) + 1

        # strategy_subgoals junction populated
        junctions = db.execute(
            "SELECT subgoal_id, position FROM strategy_subgoals "
            "WHERE strategy_id = ? ORDER BY position",
            (result.strategy_id,),
        ).fetchall()
        assert len(junctions) == 2
        assert junctions[0][1] == 0
        assert junctions[1][1] == 1

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_subgoal_files_on_disk(self, mock_lake, mock_validate, db, tmp_path):
        mock_lake.return_value = LakeResult(outcome="exhausted")

        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=1)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        bw = Backward(db, chain, config)
        result = bw.run(goal_id)

        assert result.outcome == "success"
        sg_row = db.execute(
            "SELECT lean_path FROM goals WHERE id = ?", (result.subgoal_ids[0],)
        ).fetchone()
        assert sg_row is not None
        assert Path(sg_row[0]).exists(), f"subgoal lean file missing: {sg_row[0]}"

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_commit_fault_propagates(self, mock_lake, mock_validate, db, tmp_path):
        mock_lake.return_value = LakeResult(outcome="exhausted")

        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=2)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        bw = Backward(db, chain, config)

        os.environ["COMMIT_FAULT"] = "after_step1"
        try:
            with pytest.raises(CommitFault):
                bw.run(goal_id)
        finally:
            del os.environ["COMMIT_FAULT"]

    def _setup_for_fault(self, db, tmp_path):
        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=2)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        return Backward(db, chain, config), goal_id

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_commit_fault_after_step1_consistent_recover(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        """COMMIT_FAULT=after_step1 + recover_scan: strategy + sub-goals +
        junction all DELETE'd consistently (acceptance #4)."""
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        bw, goal_id = self._setup_for_fault(db, tmp_path)
        from Tooling.commit import CommitWriter

        os.environ["COMMIT_FAULT"] = "after_step1"
        try:
            with pytest.raises(CommitFault):
                bw.run(goal_id)
        finally:
            del os.environ["COMMIT_FAULT"]

        # Pre-recover: pending rows + junction exist.
        assert db.execute(
            "SELECT COUNT(*) FROM strategies WHERE commit_state='pending'"
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM goals WHERE commit_state='pending'"
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals"
        ).fetchone()[0] == 2

        CommitWriter(db).recover_scan()

        # Post-recover: all rolled back (no files were staged).
        assert db.execute(
            "SELECT COUNT(*) FROM strategies WHERE commit_state='pending'"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM goals WHERE commit_state='pending'"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals"
        ).fetchone()[0] == 0

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_commit_fault_after_step2_consistent_recover(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        """COMMIT_FAULT=after_step2 + recover_scan: pending rows whose file was
        staged finalize 'live'; pending rows without file DELETE + cascade
        cleanup their junction edges. No FK violation."""
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        bw, goal_id = self._setup_for_fault(db, tmp_path)
        from Tooling.commit import CommitWriter

        os.environ["COMMIT_FAULT"] = "after_step2"
        try:
            with pytest.raises(CommitFault):
                bw.run(goal_id)
        finally:
            del os.environ["COMMIT_FAULT"]

        # Recover should not raise (no FK violation despite junction rows).
        CommitWriter(db).recover_scan()

        # Post-recover: no pending rows remain.
        assert db.execute(
            "SELECT COUNT(*) FROM goals WHERE commit_state='pending'"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM strategies WHERE commit_state='pending'"
        ).fetchone()[0] == 0

        # No orphan junction rows: every junction row references existing
        # strategy + goal.
        orphans = db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals sg "
            "WHERE NOT EXISTS (SELECT 1 FROM strategies s WHERE s.id = sg.strategy_id) "
            "OR NOT EXISTS (SELECT 1 FROM goals g WHERE g.id = sg.subgoal_id)"
        ).fetchone()[0]
        assert orphans == 0

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_commit_fault_after_step3_consistent_recover(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        """COMMIT_FAULT=after_step3 + recover_scan: rows already finalized in
        first step3 TX stay live; remaining pending rows finalize via lean_path
        existence. No orphan junction."""
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        bw, goal_id = self._setup_for_fault(db, tmp_path)
        from Tooling.commit import CommitWriter

        os.environ["COMMIT_FAULT"] = "after_step3"
        try:
            with pytest.raises(CommitFault):
                bw.run(goal_id)
        finally:
            del os.environ["COMMIT_FAULT"]

        CommitWriter(db).recover_scan()

        # Post-recover: no pending rows; junction rows intact (all 2).
        assert db.execute(
            "SELECT COUNT(*) FROM goals WHERE commit_state='pending'"
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT COUNT(*) FROM strategies WHERE commit_state='pending'"
        ).fetchone()[0] == 0
        # All sub-goal files were already mv'd before step3 fault, so all
        # rows finalize live; the 2 junction rows survive.
        orphans = db.execute(
            "SELECT COUNT(*) FROM strategy_subgoals sg "
            "WHERE NOT EXISTS (SELECT 1 FROM strategies s WHERE s.id = sg.strategy_id) "
            "OR NOT EXISTS (SELECT 1 FROM goals g WHERE g.id = sg.subgoal_id)"
        ).fetchone()[0]
        assert orphans == 0


# ---------------------------------------------------------------------------
# Retry staging cleanup (audit #7)
# ---------------------------------------------------------------------------


class TestRetryStaging:
    @patch("Tooling.pipelines.backward.validate")
    @patch("Tooling.pipelines.backward.run_lean")
    def test_retry_clears_stale_staging(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        """Retry must wipe the staging dir before re-running the agent so a
        prior attempt's slug-set leftovers don't leak into validator/self_verify."""
        from Tooling.stages.validator import ValidatorError
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "uses sorry"}],
        )
        # First call: validator rejects (slug_unique conflict). Second call: OK.
        mock_validate.side_effect = [
            [ValidatorError(check="slug_unique", detail="dup")],
            [],
        ]

        # Two distinct proposals across retries.
        first = {
            "combinator": "And",
            "subgoals": [{"slug": "G_root_first_x", "statement": "True -- first"}],
            "leaf_claims": [],
        }
        second = {
            "combinator": "And",
            "subgoals": [{"slug": "G_root_second_y", "statement": "True -- second"}],
            "leaf_claims": [],
        }
        chain = MagicMock(spec=FallbackChain)
        chain.run.side_effect = [
            (_make_response(first), "success"),
            (_make_response(second), "success"),
        ]

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(
            base_dir=str(tmp_path), lake_cwd=str(tmp_path), max_retries=3
        )
        bw = Backward(db, chain, config)
        result = bw.run(goal_id)
        assert result.outcome == "success"

        # After commit, sub-goal files at final lean_path. Staging dir should
        # NOT contain a leftover from the first retry's slug.
        # (Final commit also drains current-attempt staging.)
        # The pipeline's session_id is internal; instead check the staging tree
        # is clean of `G_root_first_x.lean`.
        for staging_subdir in (tmp_path / "Problems" / "test" / "Goals").rglob(
            "Staging"
        ):
            for p in staging_subdir.rglob("G_root_first_x.lean"):
                pytest.fail(f"stale staging file from retry survived: {p}")


# ---------------------------------------------------------------------------
# Pipeline row (audit #12, parity with builder.py)
# ---------------------------------------------------------------------------


class TestPipelineRow:
    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_success_writes_pipelines_row_succeeded(
        self, mock_lake, mock_validate, db, tmp_path
    ):
        mock_lake.return_value = LakeResult(
            outcome="exhausted",
            messages=[{"kind": "hasSorry", "data": "sorry"}],
        )
        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=1)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        bw = Backward(db, chain, config)
        result = bw.run(goal_id)

        assert result.outcome == "success"
        rows = db.execute(
            "SELECT kind, runtime, target_id, target_kind, status, outcome, "
            "session_id FROM pipelines"
        ).fetchall()
        assert len(rows) == 1
        kind, runtime, target_id, target_kind, status, outcome, session_id = rows[0]
        assert kind == "Backward"
        assert runtime == "atomic"
        assert target_id == str(goal_id)
        assert target_kind == "Goal"
        assert status == "succeeded"
        assert outcome == "success"
        assert session_id is not None

    def test_exhausted_writes_pipelines_row_failed(self, db, tmp_base):
        chain = MagicMock(spec=FallbackChain)
        chain.run.return_value = (None, "exhausted")
        bw = _make_backward(db, chain=chain, base_dir=tmp_base)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)
        assert result.outcome == "exhausted"

        row = db.execute(
            "SELECT kind, status, outcome FROM pipelines"
        ).fetchone()
        assert row == ("Backward", "failed", "exhausted")


# ---------------------------------------------------------------------------
# Outcome dispatch
# ---------------------------------------------------------------------------

class TestOutcomeDispatch:
    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_success_result_fields(self, mock_lake, mock_validate, db, tmp_path):
        mock_lake.return_value = LakeResult(outcome="exhausted")
        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=3)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file))
        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        bw = Backward(db, chain, config)
        result = bw.run(goal_id)

        assert result.outcome == "success"
        assert isinstance(result.strategy_id, int)
        assert len(result.subgoal_ids) == 3
        assert all(isinstance(i, int) for i in result.subgoal_ids)

    @patch("Tooling.pipelines.backward.validate", return_value=[])
    @patch("Tooling.pipelines.backward.run_lean")
    def test_depth_propagation(self, mock_lake, mock_validate, db, tmp_path):
        mock_lake.return_value = LakeResult(outcome="exhausted")
        chain = MagicMock(spec=FallbackChain)
        proposal = _simple_proposal("G_root", n=1)
        chain.run.return_value = (_make_response(proposal), "success")

        problems_dir = tmp_path / "Problems" / "test"
        problems_dir.mkdir(parents=True)
        lean_file = problems_dir / "G_root.lean"
        lean_file.write_text("theorem G_root : True := by trivial\n")

        goal_id = _insert_goal(db, lean_path=str(lean_file), depth=2)
        config = BackwardConfig(base_dir=str(tmp_path), lake_cwd=str(tmp_path))
        bw = Backward(db, chain, config)
        result = bw.run(goal_id)

        assert result.outcome == "success"
        sg_depth = db.execute(
            "SELECT depth FROM goals WHERE id = ?", (result.subgoal_ids[0],)
        ).fetchone()[0]
        assert sg_depth == 3  # parent depth(2) + 1

    def test_exhausted_returns_correct_fields(self, db, tmp_base):
        chain = MagicMock(spec=FallbackChain)
        chain.run.return_value = (None, "exhausted")
        bw = _make_backward(db, chain=chain, base_dir=tmp_base)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)
        assert result.outcome == "exhausted"
        assert result.strategy_id is None
        assert result.subgoal_ids == []

    def test_unproductive_returns_correct_fields(self, db, tmp_base):
        chain = MagicMock(spec=FallbackChain)
        proposal = {"combinator": "And", "subgoals": [], "leaf_claims": []}
        chain.run.return_value = (_make_response(proposal), "success")
        bw = _make_backward(db, chain=chain, base_dir=tmp_base)
        goal_id = _insert_goal(db)
        result = bw.run(goal_id)
        assert result.outcome == "unproductive"
        assert result.strategy_id is None
        assert result.subgoal_ids == []
