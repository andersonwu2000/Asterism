"""Unit tests for Tooling/pipelines/refuter.py (P4 C29)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Tooling.db.connect import connect, init_schema
from Tooling.lake import LakeResult
from Tooling.agent.provider import AgentResponse, FallbackChain
from Tooling.pipelines.refuter import Refuter, RefuterConfig, RefuterResult


# ---------------------------------------------------------------------------
# Fixtures
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
    """Force-miss dedupe so non-Counterexample paths exercise novel commit
    by default; tests that need hit override locally."""
    monkeypatch.setenv("DEDUPE_MOCK", "force_miss")


def _insert_goal(
    conn,
    problem: str = "test",
    slug: str = "G",
    lean_path: str | None = None,
    kind: str = "conjecture",
    question: str = "True",
    evidence: str | None = None,
) -> int:
    if lean_path is None:
        lean_path = f"Problems/{problem}/{slug}.lean"
    with conn:
        cur = conn.execute(
            "INSERT INTO goals "
            "(problem, slug, lean_path, origin, kind, status, commit_state, "
            "created_at, updated_at, depth, question, evidence) "
            "VALUES (?, ?, ?, 'root', ?, 'open', 'live', "
            "datetime('now'), datetime('now'), 0, ?, ?)",
            (problem, slug, lean_path, kind, question, evidence),
        )
    return cur.lastrowid  # type: ignore[return-value]


def _make_refuter(
    db,
    chain: FallbackChain | None = None,
    base_dir: str | None = None,
    lake_cwd: str = ".",
    max_retries: int = 3,
) -> Refuter:
    if chain is None:
        chain = MagicMock(spec=FallbackChain)
    if base_dir is None:
        base_dir = tempfile.mkdtemp()
    return Refuter(db, chain,
                   RefuterConfig(base_dir=base_dir, lake_cwd=lake_cwd,
                                 max_retries=max_retries))


def _agent_response(negation: dict, session_id: str = "s1") -> AgentResponse:
    return AgentResponse(
        output=f"```json\n{json.dumps(negation)}\n```",
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TestParseNegation:
    def test_valid_json(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        out = '```json\n{"negation_slug":"neg_g","negation_statement":"False"}\n```'
        result = r._parse_negation(out)
        assert result == {"negation_slug": "neg_g", "negation_statement": "False"}

    def test_no_code_block(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        assert r._parse_negation("just text") is None

    def test_malformed_json(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        assert r._parse_negation("```json\n{broken\n```") is None

    def test_missing_slug(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        out = '```json\n{"negation_statement":"False"}\n```'
        assert r._parse_negation(out) is None

    def test_missing_statement(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        out = '```json\n{"negation_slug":"x"}\n```'
        assert r._parse_negation(out) is None

    def test_empty_slug_or_statement(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        out1 = '```json\n{"negation_slug":"","negation_statement":"False"}\n```'
        out2 = '```json\n{"negation_slug":"x","negation_statement":""}\n```'
        assert r._parse_negation(out1) is None
        assert r._parse_negation(out2) is None

    def test_top_level_not_dict(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        out = '```json\n["a","b"]\n```'
        assert r._parse_negation(out) is None


# ---------------------------------------------------------------------------
# Witness extraction (D-13-1 reserve slot)
# ---------------------------------------------------------------------------

class TestEvidenceWitnessBlock:
    def test_no_evidence_returns_none(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        assert r._extract_witness_block({}) == "(none)"

    def test_empty_evidence_returns_none(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        assert r._extract_witness_block({"evidence": ""}) == "(none)"

    def test_evidence_dict_no_witness(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        ev = json.dumps({"some_other_key": 1})
        assert r._extract_witness_block({"evidence": ev}) == "(none)"

    def test_evidence_with_witness(self, db, tmp_base):
        """When Counterexample lands and writes witness, prompt block fills."""
        r = _make_refuter(db, base_dir=tmp_base)
        ev = json.dumps({
            "counterexample_witness": {
                "witness_lean_expr": "(2 : Nat)",
                "witness_type": "Nat",
                "predicate_def": "myPred",
            }
        })
        block = r._extract_witness_block({"evidence": ev})
        assert "(2 : Nat)" in block
        assert "Nat" in block
        assert "myPred" in block

    def test_malformed_json_evidence_fallthrough(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        assert r._extract_witness_block({"evidence": "{not json"}) == "(none)"

    def test_witness_missing_expr_returns_none(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        ev = json.dumps({"counterexample_witness": {"witness_type": "Nat"}})
        assert r._extract_witness_block({"evidence": ev}) == "(none)"


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_substitutes_placeholders(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        goal = {
            "problem": "P", "slug": "g", "question": "∀ n, P n", "evidence": None,
        }
        prompt = r._build_prompt(goal, [])
        assert "∀ n, P n" in prompt
        assert "{{GOAL_STATEMENT}}" not in prompt
        assert "{{DEAD_ATTEMPTS}}" not in prompt
        assert "{{EVIDENCE_WITNESS}}" not in prompt

    def test_witness_block_in_prompt(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        ev = json.dumps({
            "counterexample_witness": {
                "witness_lean_expr": "(7 : Nat)",
                "witness_type": "Nat",
                "predicate_def": "P",
            }
        })
        prompt = r._build_prompt(
            {"problem": "P", "slug": "g", "question": "True", "evidence": ev}, [])
        assert "(7 : Nat)" in prompt

    def test_no_witness_block_says_none(self, db, tmp_base):
        r = _make_refuter(db, base_dir=tmp_base)
        prompt = r._build_prompt(
            {"problem": "P", "slug": "g", "question": "True", "evidence": None}, [])
        # The "(none)" sentinel must appear so agent knows to take generic path
        assert "(none)" in prompt


# ---------------------------------------------------------------------------
# self_verify
# ---------------------------------------------------------------------------

class TestSelfVerify:
    def test_pass_only_hassorry(self, db, tmp_base, tmp_path):
        r = _make_refuter(db, base_dir=tmp_base)
        f = tmp_path / "neg.lean"
        f.write_text("theorem neg : False := sorry", encoding="utf-8")
        with patch(
            "Tooling.pipelines.refuter.run_lean",
            return_value=LakeResult(outcome="exhausted",
                                    messages=[{"kind": "hasSorry"}]),
        ):
            assert r._self_verify({"staging_path": str(f)}) is True

    def test_fail_on_error_message(self, db, tmp_base, tmp_path):
        r = _make_refuter(db, base_dir=tmp_base)
        f = tmp_path / "neg.lean"
        f.write_text("oops", encoding="utf-8")
        with patch(
            "Tooling.pipelines.refuter.run_lean",
            return_value=LakeResult(outcome="exhausted",
                                    messages=[{"kind": "error",
                                               "data": "type error"}]),
        ):
            assert r._self_verify({"staging_path": str(f)}) is False

    def test_fail_on_timeout(self, db, tmp_base, tmp_path):
        r = _make_refuter(db, base_dir=tmp_base)
        f = tmp_path / "neg.lean"
        f.write_text("ok", encoding="utf-8")
        with patch(
            "Tooling.pipelines.refuter.run_lean",
            return_value=LakeResult(outcome="exhausted", timed_out=True),
        ):
            assert r._self_verify({"staging_path": str(f)}) is False


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------

class TestDedupeAgainstExisting:
    def test_force_miss_returns_none(self, db, tmp_base, monkeypatch, tmp_path):
        monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
        _insert_goal(db, slug="seed_goal", question="True")
        r = _make_refuter(db, base_dir=tmp_base)
        f = tmp_path / "neg.lean"
        f.write_text("ok", encoding="utf-8")
        result = r._dedupe_against_existing(
            {"staging_path": str(f), "negation_slug": "n"}, {"problem": "test"})
        assert result is None

    def test_no_entries_returns_none(self, db, tmp_base, tmp_path):
        # No live goals with problem='test' → entries empty → dedupe skipped.
        r = _make_refuter(db, base_dir=tmp_base)
        f = tmp_path / "neg.lean"
        f.write_text("ok", encoding="utf-8")
        result = r._dedupe_against_existing(
            {"staging_path": str(f), "negation_slug": "n"}, {"problem": "test"})
        assert result is None

    def test_force_hit_returns_entry_id(self, db, tmp_base, monkeypatch, tmp_path):
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        gid = _insert_goal(db, slug="existing_neg", question="False")
        r = _make_refuter(db, base_dir=tmp_base)
        f = tmp_path / "neg.lean"
        f.write_text("theorem neg : False := sorry", encoding="utf-8")
        result = r._dedupe_against_existing(
            {"staging_path": str(f), "negation_slug": "n"}, {"problem": "test"})
        assert result == gid

    def test_problem_scope_filter(self, db, tmp_base, monkeypatch, tmp_path):
        """Dedupe entries are scoped to parent's Problem only."""
        monkeypatch.setenv("DEDUPE_MOCK", "force_hit")
        # Two seeds in different problems
        _insert_goal(db, problem="A", slug="A_seed",
                     lean_path="Problems/A/A_seed.lean")
        _insert_goal(db, problem="B", slug="B_seed",
                     lean_path="Problems/B/B_seed.lean")
        r = _make_refuter(db, base_dir=tmp_base)
        f = tmp_path / "neg.lean"
        f.write_text("theorem n : False := sorry", encoding="utf-8")

        captured: list[list[dict]] = []

        def fake_dedupe(cand_path, entries, **kwargs):
            from Tooling.subsystems.dedupe import DedupeResult
            captured.append(list(entries))
            return DedupeResult(outcome="novel")

        with patch("Tooling.pipelines.refuter._stage_dedupe",
                   side_effect=fake_dedupe):
            r._dedupe_against_existing(
                {"staging_path": str(f), "negation_slug": "n"},
                {"problem": "A"})
        assert len(captured) == 1
        paths = [e["lean_path"] for e in captured[0]]
        assert any("/A/" in p for p in paths)
        assert not any("/B/" in p for p in paths)


# ---------------------------------------------------------------------------
# Commit (novel)
# ---------------------------------------------------------------------------

class TestCommitNovel:
    def test_inserts_negation_goal_with_twin_of(self, db, tmp_base):
        gid = _insert_goal(db, slug="g_root", problem="P",
                           question="∀ n, P n")
        r = _make_refuter(db, base_dir=tmp_base)
        staging_path = Path(tmp_base) / "stage" / "neg_g_root.lean"
        staging_path.parent.mkdir(parents=True)
        staging_path.write_text("theorem neg_g_root : ∃ n, ¬ P n := sorry",
                                encoding="utf-8")

        goal = {"id": gid, "problem": "P", "slug": "g_root",
                "question": "∀ n, P n"}
        neg_id = r._commit_novel(goal, {
            "negation_slug": "neg_g_root",
            "negation_statement": "∃ n, ¬ P n",
            "staging_path": str(staging_path),
        }, pipeline_id="pid_x")

        # ¬G goal exists with origin='refuter_negation', kind='theorem',
        # twin_of=G.id, status='open', commit_state='live'
        row = db.execute(
            "SELECT origin, kind, status, commit_state, twin_of, depth "
            "FROM goals WHERE id = ?", (neg_id,)).fetchone()
        assert row[0] == "refuter_negation"
        assert row[1] == "theorem"
        assert row[2] == "open"
        assert row[3] == "live"
        assert row[4] == gid
        assert row[5] == 0

        # G now has twin_of pointing back to ¬G
        g_row = db.execute(
            "SELECT twin_of FROM goals WHERE id = ?", (gid,)).fetchone()
        assert g_row[0] == neg_id

    def test_lean_file_moved_from_staging(self, db, tmp_base):
        gid = _insert_goal(db, slug="g", problem="P", question="True")
        r = _make_refuter(db, base_dir=tmp_base)
        staging_path = Path(tmp_base) / "stage" / "neg_g.lean"
        staging_path.parent.mkdir(parents=True)
        staging_path.write_text("theorem neg_g : False := sorry",
                                encoding="utf-8")
        goal = {"id": gid, "problem": "P", "slug": "g", "question": "True"}
        r._commit_novel(goal, {
            "negation_slug": "neg_g",
            "negation_statement": "False",
            "staging_path": str(staging_path),
        }, pipeline_id="pid_y")
        # staging moved
        assert not staging_path.exists()
        final = Path(tmp_base) / "Problems" / "P" / "Goals" / "neg_g.lean"
        assert final.exists()
        assert "theorem neg_g" in final.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Commit (dup)
# ---------------------------------------------------------------------------

class TestCommitDup:
    def test_dup_only_updates_twin_of_bidirectional(self, db, tmp_base):
        gid = _insert_goal(db, slug="g", problem="P", question="True")
        # Pre-existing ¬G that dedupe matched against
        existing_neg_id = _insert_goal(
            db, slug="existing_neg_g", problem="P",
            lean_path="Problems/P/existing_neg_g.lean", question="False")
        r = _make_refuter(db, base_dir=tmp_base)
        goal = {"id": gid, "problem": "P", "slug": "g", "question": "True"}
        returned = r._commit_dup(goal, existing_neg_id)
        assert returned == existing_neg_id
        # Bidirectional twin_of set
        g_row = db.execute(
            "SELECT twin_of FROM goals WHERE id = ?", (gid,)).fetchone()
        neg_row = db.execute(
            "SELECT twin_of FROM goals WHERE id = ?",
            (existing_neg_id,)).fetchone()
        assert g_row[0] == existing_neg_id
        assert neg_row[0] == gid


# ---------------------------------------------------------------------------
# run() — env hooks
# ---------------------------------------------------------------------------

class TestRunHooks:
    def test_force_exhausted(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("REFUTER_FORCE", "exhausted")
        r = _make_refuter(db, base_dir=tmp_base)
        result = r.run(goal_id=999)
        assert result.outcome == "exhausted"

    def test_force_succeed(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("REFUTER_FORCE", "succeed")
        r = _make_refuter(db, base_dir=tmp_base)
        result = r.run(goal_id=999)
        assert result.outcome == "success"
        assert result.negation_goal_id is None

    def test_unknown_force_raises(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("REFUTER_FORCE", "bogus")
        r = _make_refuter(db, base_dir=tmp_base)
        with pytest.raises(ValueError, match="unknown REFUTER_FORCE"):
            r.run(goal_id=1)

    def test_unknown_mock_raises(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("REFUTER_MOCK", "bogus")
        r = _make_refuter(db, base_dir=tmp_base)
        with pytest.raises(ValueError, match="unknown REFUTER_MOCK"):
            r.run(goal_id=1)

    def test_mock_success_negation(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("REFUTER_MOCK", "success_negation")
        gid = _insert_goal(db, slug="my_g", problem="P", question="True")
        r = _make_refuter(db, base_dir=tmp_base)
        result = r.run(goal_id=gid)
        assert result.outcome == "success"
        assert result.negation_goal_id is not None
        # ¬G inserted with bidirectional twin
        row = db.execute(
            "SELECT slug, origin, twin_of FROM goals WHERE id = ?",
            (result.negation_goal_id,)).fetchone()
        assert row[0] == "neg_my_g"
        assert row[1] == "refuter_negation"
        assert row[2] == gid


# ---------------------------------------------------------------------------
# run() — end-to-end (mocked agent + LAKE_MOCK)
# ---------------------------------------------------------------------------

class TestRunEndToEnd:
    def test_novel_full_loop(self, db, tmp_base, monkeypatch):
        """Agent returns valid negation → self_verify pass (LAKE_MOCK=sorry,
        sorry-only message) → dedupe miss → commit_novel."""
        monkeypatch.setenv("LAKE_MOCK", "sorry")  # passes self_verify
        monkeypatch.setenv("DEDUPE_MOCK", "force_miss")
        gid = _insert_goal(db, slug="g_full", problem="P", question="∀ n, P n")
        chain = MagicMock(spec=FallbackChain)
        chain.run.return_value = (
            _agent_response({"negation_slug": "neg_g_full",
                             "negation_statement": "∃ n, ¬ P n"}),
            "success",
        )
        r = _make_refuter(db, chain=chain, base_dir=tmp_base)
        result = r.run(goal_id=gid)
        assert result.outcome == "success"
        assert result.deduped is False
        # ¬G inserted with twin_of=gid; G.twin_of=neg_id
        row = db.execute(
            "SELECT origin, twin_of FROM goals WHERE id = ?",
            (result.negation_goal_id,)).fetchone()
        assert row[0] == "refuter_negation"
        assert row[1] == gid
        g_twin = db.execute(
            "SELECT twin_of FROM goals WHERE id = ?", (gid,)).fetchone()[0]
        assert g_twin == result.negation_goal_id

    def test_agent_returns_none_exhausted(self, db, tmp_base, monkeypatch):
        """Provider chain returns ('failure', None) → exhausted on first try."""
        gid = _insert_goal(db, slug="g_x", problem="P", question="True")
        chain = MagicMock(spec=FallbackChain)
        chain.run.return_value = (None, "failure")
        r = _make_refuter(db, chain=chain, base_dir=tmp_base, max_retries=2)
        result = r.run(goal_id=gid)
        assert result.outcome == "exhausted"

    def test_malformed_json_retries_then_exhausted(self, db, tmp_base, monkeypatch):
        gid = _insert_goal(db, slug="g_y", problem="P", question="True")
        chain = MagicMock(spec=FallbackChain)
        chain.run.return_value = (
            AgentResponse(output="no json", session_id="s1"), "success",
        )
        r = _make_refuter(db, chain=chain, base_dir=tmp_base, max_retries=2)
        result = r.run(goal_id=gid)
        assert result.outcome == "exhausted"
        # Provider was called max_retries times
        assert chain.run.call_count == 2

    def test_self_verify_fail_retries(self, db, tmp_base, monkeypatch):
        """self_verify fail (lake error) → loop retries."""
        monkeypatch.setenv("LAKE_MOCK", "sorry")
        gid = _insert_goal(db, slug="g_z", problem="P", question="True")
        chain = MagicMock(spec=FallbackChain)
        # Returns valid JSON; we monkeypatch _self_verify to fail twice then pass
        chain.run.return_value = (
            _agent_response({"negation_slug": "neg_g_z",
                             "negation_statement": "False"}),
            "success",
        )
        r = _make_refuter(db, chain=chain, base_dir=tmp_base, max_retries=3)
        verify_calls = {"n": 0}

        def fake_verify(neg_file):
            verify_calls["n"] += 1
            return verify_calls["n"] >= 3  # pass on 3rd try

        with patch.object(r, "_self_verify", side_effect=fake_verify):
            with patch.object(r, "_dedupe_against_existing", return_value=None):
                result = r.run(goal_id=gid)
        assert result.outcome == "success"
        assert verify_calls["n"] == 3

    def test_dup_path_returns_existing_id(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("LAKE_MOCK", "sorry")
        gid = _insert_goal(db, slug="g_dup", problem="P", question="True")
        existing_neg = _insert_goal(
            db, slug="existing_neg", problem="P",
            lean_path="Problems/P/existing_neg.lean", question="False")
        chain = MagicMock(spec=FallbackChain)
        chain.run.return_value = (
            _agent_response({"negation_slug": "neg_g_dup",
                             "negation_statement": "False"}),
            "success",
        )
        r = _make_refuter(db, chain=chain, base_dir=tmp_base)
        with patch.object(r, "_dedupe_against_existing",
                          return_value=existing_neg):
            result = r.run(goal_id=gid)
        assert result.outcome == "success"
        assert result.deduped is True
        assert result.negation_goal_id == existing_neg
        # G's twin_of points to existing
        g_twin = db.execute(
            "SELECT twin_of FROM goals WHERE id = ?", (gid,)).fetchone()[0]
        assert g_twin == existing_neg


# ---------------------------------------------------------------------------
# Pipelines table parity
# ---------------------------------------------------------------------------

class TestPipelinesRow:
    def test_pipeline_inserted_and_finished(self, db, tmp_base, monkeypatch):
        monkeypatch.setenv("REFUTER_FORCE", "exhausted")
        gid = _insert_goal(db, slug="g_pipe", problem="P")
        r = _make_refuter(db, base_dir=tmp_base)
        # FORCE returns early (no pipeline row created); switch to MOCK
        # which DOES go through pipeline INSERT/finish path.
        monkeypatch.delenv("REFUTER_FORCE", raising=False)
        monkeypatch.setenv("REFUTER_MOCK", "success_negation")
        result = r.run(goal_id=gid)
        assert result.outcome == "success"
        rows = db.execute(
            "SELECT kind, runtime, target_id, target_kind, status, outcome "
            "FROM pipelines"
        ).fetchall()
        assert len(rows) == 1
        kind, runtime, tgt_id, tgt_kind, status, outcome = rows[0]
        assert kind == "Refuter"
        assert runtime == "atomic"
        assert tgt_id == str(gid)
        assert tgt_kind == "Goal"
        assert status == "succeeded"
        assert outcome == "success"
