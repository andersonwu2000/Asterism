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

class TestStubStages:
    def test_failure_replay_returns_empty(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        assert bw.failure_replay("pipeline-1") == []

    def test_find_lemmas_returns_empty(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        assert bw.find_lemmas({"problem": "test", "slug": "g"}) == []

    def test_find_subgoals_returns_empty(self, db, tmp_base):
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

class TestNormalizeHash:
    def test_whitespace_collapsed(self):
        h1 = Backward._normalize_hash("∀  n  :  ℕ,  n + 0 = n")
        h2 = Backward._normalize_hash("∀ n : ℕ, n + 0 = n")
        assert h1 == h2

    def test_leading_trailing_stripped(self):
        h1 = Backward._normalize_hash("  True  ")
        h2 = Backward._normalize_hash("True")
        assert h1 == h2

    def test_different_statements_differ(self):
        assert Backward._normalize_hash("True") != Backward._normalize_hash("False")


class TestDedupe:
    def test_new_statement_passes(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        subgoals = [{"slug": "sub1", "statement": "1 + 1 = 2"}]
        result = bw._dedupe(subgoals)
        assert len(result) == 1
        assert "statement_hash" in result[0]

    def test_existing_hash_filtered(self, db, tmp_base):
        statement = "∀ n : ℕ, n + 0 = n"
        h = Backward._normalize_hash(statement)
        with db:
            db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, statement_hash, origin, kind, status, "
                "commit_state, created_at, updated_at) "
                "VALUES ('test', 'existing', 'Problems/test/existing.lean', ?, "
                "'root', 'theorem', 'open', 'live', datetime('now'), datetime('now'))",
                (h,),
            )
        bw = _make_backward(db, base_dir=tmp_base)
        result = bw._dedupe([{"slug": "sub1", "statement": statement}])
        assert result == []

    def test_hash_stored_in_result(self, db, tmp_base):
        bw = _make_backward(db, base_dir=tmp_base)
        subgoals = [{"slug": "s1", "statement": "True"}]
        result = bw._dedupe(subgoals)
        expected_hash = Backward._normalize_hash("True")
        assert result[0]["statement_hash"] == expected_hash

    def test_partial_dedupe(self, db, tmp_base):
        existing_stmt = "∀ n : ℕ, n = n"
        h = Backward._normalize_hash(existing_stmt)
        with db:
            db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, statement_hash, origin, kind, status, "
                "commit_state, created_at, updated_at) "
                "VALUES ('test', 'dup', 'Problems/test/dup.lean', ?, "
                "'root', 'theorem', 'open', 'live', datetime('now'), datetime('now'))",
                (h,),
            )
        bw = _make_backward(db, base_dir=tmp_base)
        subgoals = [
            {"slug": "sub1", "statement": existing_stmt},
            {"slug": "sub2", "statement": "True"},
        ]
        result = bw._dedupe(subgoals)
        assert len(result) == 1
        assert result[0]["slug"] == "sub2"

    def test_intra_proposal_dedupe(self, db, tmp_base):
        """Two sub-goals in the same proposal sharing a statement should
        collapse to one — agent occasionally proposes redundant sub-goals."""
        bw = _make_backward(db, base_dir=tmp_base)
        subgoals = [
            {"slug": "sub1", "statement": "1 + 1 = 2"},
            {"slug": "sub2", "statement": "1 + 1 = 2"},  # duplicate stmt
            {"slug": "sub3", "statement": "2 + 2 = 4"},
        ]
        result = bw._dedupe(subgoals)
        assert len(result) == 2
        assert {sg["slug"] for sg in result} == {"sub1", "sub3"}


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

    def test_unproductive_all_dupes(self, db, tmp_base):
        stmt = "True"
        h = Backward._normalize_hash(stmt)
        with db:
            db.execute(
                "INSERT INTO goals "
                "(problem, slug, lean_path, statement_hash, origin, kind, status, "
                "commit_state, created_at, updated_at) "
                "VALUES ('test', 'dup', 'Problems/test/dup.lean', ?, "
                "'root', 'theorem', 'open', 'live', datetime('now'), datetime('now'))",
                (h,),
            )
        chain = MagicMock(spec=FallbackChain)
        proposal = {
            "combinator": "And",
            "subgoals": [{"slug": "sub1", "statement": stmt}],
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
