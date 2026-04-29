"""Backward pipeline runtime (P2).

Stage sequence:
  failure_replay → find_lemmas (stub) → find_subgoals (stub) →
  agent → dedupe (local) → validator → self_verify (per-file) → commit

P2 → P3 upgrade points:
  - self_verify is per-file (loops `lake env lean --json <single>`); spec calls
    for "lake build staging dir" multi-file mode. P2 demo theorems have no
    cross-file imports between sub-goals, so per-file is functionally equivalent.
    P3 should add `Tooling.lake.run_lean_multi(staging_dir, ...)` and switch.
  - The strategy `.lean` file written by Backward is a comment-only stub; the
    real proof body (combining sub-goals) is written by Builder when each
    sub-goal proves (C14 Builder upgrade).
  - failure_replay / find_lemmas / find_subgoals are stubs returning empty;
    real implementations land in P3 (find_lemmas / find_subgoals via search
    cache) and P2.Builder upgrade (Backward.failure_replay reads dead_attempts).

Public API:
  Backward(conn, chain, config, resolver=None)
  Backward.run(goal_id) -> BackwardResult
"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sqlite3

from Tooling.commit import CommitWriter
from Tooling.lake import run_lean
from Tooling.stages.failure_replay import failure_replay as _stage_failure_replay
from Tooling.stages.find_lemmas import find_lemmas as _stage_find_lemmas
from Tooling.stages.find_subgoals import find_subgoals as _stage_find_subgoals
from Tooling.stages.validator import validate
from Tooling.subsystems.dedupe import dedupe as _stage_dedupe
from Tooling.subsystems.similarity import parent_subgoal_max_similarity
from Tooling.agent.provider import AgentResponse, FallbackChain, ModelResolver


_VALID_COMBINATORS: frozenset[str] = frozenset({"And", "Or", "Exists", "Leaf"})


def _is_decompose_required(goal: dict) -> bool:
    """P6.x patch 24: read per-Goal `decompose_required` flag from
    goals.evidence JSON. When True, Backward MUST produce Path B —
    Leaf proposals are rejected by the parser as if malformed.
    """
    ev_raw = goal.get("evidence")
    if not ev_raw:
        return False
    try:
        ev = json.loads(ev_raw) if isinstance(ev_raw, str) else ev_raw
    except json.JSONDecodeError:
        return False
    return bool(ev.get("decompose_required", False)) if isinstance(ev, dict) else False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_as_dict(conn: sqlite3.Connection, table: str, row_id: int) -> dict[str, Any]:
    cur = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"{table} row {row_id} not found")
    return dict(zip([d[0] for d in cur.description], row))


@dataclass
class BackwardConfig:
    base_dir: str         # workspace root (Problems/ lives here)
    lake_cwd: str         # cwd for lake subprocess
    max_retries: int = 3  # max agent+validator cycle iterations
    lean_timeout: float = 600.0  # per-subgoal lake timeout (seconds)


@dataclass
class BackwardResult:
    outcome: str          # "success" | "exhausted" | "unproductive"
    strategy_id: int | None = None
    subgoal_ids: list[int] = field(default_factory=list)


class Backward:
    def __init__(
        self,
        conn: sqlite3.Connection,
        chain: FallbackChain,
        config: BackwardConfig,
        resolver: ModelResolver | None = None,
    ) -> None:
        self.conn = conn
        self.chain = chain
        self.config = config
        self.resolver = resolver or ModelResolver()

    # ------------------------------------------------------------------
    # Stage: failure_replay (P3 C22 — delegates to Tooling.stages module)
    # ------------------------------------------------------------------

    def failure_replay(self, goal_id: int) -> list[dict]:
        """Read up to K_digest most recent dead_attempts for the goal.

        Backward operates at Goal target_kind (Builder uses Strategy).
        K_digest defaults to 5 per phase3 §Config; pass goal_id directly
        instead of pipeline_id (P2 stub took pipeline_id and returned [];
        C22 makes this Goal-scoped to feed prior decomposition failures
        back into the agent prompt).
        """
        return _stage_failure_replay(self.conn, goal_id, "Goal")

    # ------------------------------------------------------------------
    # Stage: find_lemmas (P3 C22 — delegates to Tooling.stages module)
    # ------------------------------------------------------------------

    def find_lemmas(self, goal: dict) -> list[dict]:
        """Return candidate lemmas from mathlib + library scopes.

        P6.x patch 28: library scope is now DB-backed (returns proved
        siblings in the same Problem); mathlib remains stub-empty.

        Each entry: {"name": slug, "type": question, "score": float}.
        The full dict (not just names) is forwarded to `_build_prompt`
        so the agent sees the proven sibling's statement type and can
        cite it via Lean import.
        """
        return _stage_find_lemmas(self.conn, goal,
                                  lake_cwd=self.config.lake_cwd)

    # ------------------------------------------------------------------
    # Stage: find_subgoals (P3 C22 — delegates to Tooling.stages module)
    # ------------------------------------------------------------------

    def find_subgoals(self, goal: dict) -> list[dict]:
        """Return existing local Goals reusable as sub-goals (current Problem)."""
        return _stage_find_subgoals(self.conn, goal)

    # ------------------------------------------------------------------
    # Stage: agent
    # ------------------------------------------------------------------

    def _load_prompt_template(self) -> str:
        prompt_path = Path(__file__).parents[2] / "docs" / "prompts" / "backward.md"
        return prompt_path.read_text(encoding="utf-8")

    def _build_prompt(
        self,
        goal: dict,
        dead_attempts: list[dict],
        candidate_lemmas: list[dict] | None = None,
    ) -> str:
        template = self._load_prompt_template()
        dead_str = json.dumps(dead_attempts, indent=2) if dead_attempts else "[]"
        # P6.x patch 28: wire find_lemmas results into the prompt under
        # `{{CANDIDATE_LEMMAS}}`. Library scope is DB-backed and surfaces
        # proved siblings in the same Problem; the agent can `exact
        # Problems.<p>.<slug>` them in Path A.
        if candidate_lemmas:
            cand_str = json.dumps(
                [
                    {"name": c.get("name", ""),
                     "type": c.get("type", "")}
                    for c in candidate_lemmas
                    if c.get("name")
                ],
                indent=2,
            )
        else:
            cand_str = "[]"
        prompt = (
            template
            .replace("{{GOAL_PROBLEM}}", goal.get("problem") or "")
            .replace("{{GOAL_SLUG}}", goal.get("slug") or "")
            .replace("{{GOAL_STATEMENT}}", goal.get("question") or "")
            .replace("{{DEAD_ATTEMPTS}}", dead_str)
            .replace("{{CANDIDATE_LEMMAS}}", cand_str)
        )
        # P6.x patch 24: per-Goal `decompose_required` framework hard
        # limit (stored in goals.evidence JSON). When set, prepend a
        # directive so the agent ONLY produces Path B (decomposition);
        # _parse_proposal rejects `combinator: "Leaf"` further down so
        # the constraint is doubly enforced.
        if _is_decompose_required(goal):
            prompt = (
                "## FRAMEWORK CONSTRAINT (hard, non-negotiable)\n\n"
                "This Goal is marked `decompose_required: true`. You MUST"
                " produce a Path B decomposition (combinator And / Or /"
                " Exists with non-empty `subgoals`). Path A (Leaf) is"
                " REJECTED by the framework parser regardless of what"
                " you propose. Even if you believe Mathlib has a one-"
                "shot proof, do NOT use Leaf — propose 2-8 sub-goals.\n\n"
                + prompt
            )
        return prompt

    def _run_agent(
        self,
        goal: dict,
        dead_attempts: list[dict],
        session_id: str,
        staging_dir: str,
        candidate_lemmas: list[dict] | None = None,
    ) -> AgentResponse | None:
        model_tier = self.resolver.resolve("backward", "agent")
        prompt = self._build_prompt(goal, dead_attempts, candidate_lemmas)
        response, outcome = self.chain.run(
            model_tier=model_tier,
            prompt=prompt,
            scope_dirs=[staging_dir],
            session_id=session_id,
            staging_dir=staging_dir,
        )
        return response if outcome == "success" else None

    # ------------------------------------------------------------------
    # Stage: parse PROPOSAL from agent output
    # ------------------------------------------------------------------

    def _parse_proposal(self, output: str, goal: dict | None = None) -> dict | None:
        """Extract + schema-validate PROPOSAL from agent output.

        Requires a ```json ... ``` code block as specified in backward.md.
        Returns None (→ caller retries) if any of:
          - no JSON code block / malformed JSON
          - top-level not a dict
          - combinator not in {And, Or, Exists, Leaf}
          - subgoals not a list
          - any sub-goal not a dict, or missing non-empty 'slug' / 'statement'

        P6.x patch 24: when *goal* has `decompose_required: true` in
        evidence, additionally reject `combinator: "Leaf"` (force Path B).
        """
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', output)
        if not m:
            return None
        try:
            obj = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        if obj.get("combinator") not in _VALID_COMBINATORS:
            return None
        # P6.x patch 3: Leaf path requires `proof` field, no subgoals.
        if obj.get("combinator") == "Leaf":
            # P6.x patch 24: framework hard limit — reject Leaf when
            # the Goal has `decompose_required: true` in evidence.
            if goal is not None and _is_decompose_required(goal):
                return None
            proof = obj.get("proof")
            if not isinstance(proof, str) or not proof.strip():
                return None
            return obj
        subgoals = obj.get("subgoals")
        if not isinstance(subgoals, list):
            return None
        for sg in subgoals:
            if not isinstance(sg, dict):
                return None
            slug = sg.get("slug")
            if not isinstance(slug, str) or not slug:
                return None
            statement = sg.get("statement")
            if not isinstance(statement, str) or not statement:
                return None
        return obj

    # ------------------------------------------------------------------
    # Stage: dedupe (local) — dedupe.lean via Tooling.subsystems.dedupe
    # ------------------------------------------------------------------

    def _dedupe(
        self,
        subgoals: list[dict],
        staging_dir: str,
        goal: dict,
    ) -> list[dict]:
        """Remove subgoals duplicating an existing live Goal or another
        sub-goal in the same proposal.

        P3 C23 fully replaces the P2 statement_hash short-circuit with
        dedupe.lean (Lean.Meta.isDefEq strict mode). Each candidate
        sub-goal is written to a temporary staging .lean file then compared
        against the entries list (live goals in DB) via subprocess.

        Entries are scoped to the parent goal's Problem (spec
        phase3_cache.md §Demo D1: "dedupe (local)" — local = single-Problem
        scope). Cross-Problem hits would silently drop sub-goals whose
        cross-Problem entry can't even be imported into Problem B's lake env.

        Returns the unique sub-goals (statement_hash field is no longer
        populated; spec §C23 directs full replacement of statement_hash
        code, leaving the column NULL for new sub-goals).
        """
        # Build entries list from live goals scoped to parent goal's Problem.
        problem = goal["problem"]
        entry_rows = self.conn.execute(
            "SELECT id, lean_path FROM goals "
            "WHERE commit_state = 'live' AND problem = ?",
            (problem,),
        ).fetchall()
        entries = [{"id": int(r[0]), "lean_path": str(r[1])} for r in entry_rows]

        seen_hashes: set[str] = set()
        unique: list[dict] = []
        for sg in subgoals:
            statement = sg.get("statement", "")
            # Within-proposal dedup is text-equal only (P2-equivalent
            # behavior); isDefEq is reserved for the candidate-vs-DB-entry
            # path below. α-equiv siblings within the same proposal would
            # slip through but commit's slug_unique constraint catches the
            # realistic conflict.
            text_key = statement.strip()
            if text_key in seen_hashes:
                continue

            # Build a temporary candidate file for dedupe.lean.
            slug = sg.get("slug", f"sg_{len(unique)}")
            cand_path = Path(staging_dir) / f"_dedupe_cand_{slug}.lean"
            cand_path.parent.mkdir(parents=True, exist_ok=True)
            cand_path.write_text(
                f"theorem _candidate : {statement} := sorry\n",
                encoding="utf-8",
            )

            try:
                result = _stage_dedupe(
                    cand_path,
                    entries,
                    conn=self.conn,
                    mode="strict",
                )
            finally:
                cand_path.unlink(missing_ok=True)

            if result.outcome == "hit":
                # Already exists as goal entry_id — skip.
                continue
            if result.outcome == "timeout":
                # phase3 §風險 line 230 字面允許 NOVEL fallback on timeout;
                # cache does NOT cache timeout (dedupe.py:287 only caches
                # hit/novel). Surface to stderr so a stretch of timeouts
                # is visible during P3 demo D1 — silent fallthrough was
                # the C13–C22 silent-failure red-line failure mode.
                import sys
                print(
                    f"[backward._dedupe] timeout for sub-goal {slug!r}; "
                    "treated as novel per spec §風險",
                    file=sys.stderr,
                )
            seen_hashes.add(text_key)
            unique.append(sg)
        return unique

    # ------------------------------------------------------------------
    # Write staging .lean sorry stubs
    # ------------------------------------------------------------------

    def _write_staging_files(
        self, subgoals: list[dict], staging_dir: str, goal: dict
    ) -> list[dict]:
        staging = Path(staging_dir)
        staging.mkdir(parents=True, exist_ok=True)
        subgoals_dir = (
            Path(self.config.base_dir)
            / "Problems" / goal["problem"]
            / "Goals" / f"{goal['id']}_{goal['slug']}"
            / "SubGoals"
        )
        # P6.x patch 25: subgoal staging .lean files must import the
        # per-Problem Defs so validator's runFrontend can elaborate them
        # (subgoal statements typically reference Mathlib types like ℕ,
        # ℝ, Function.Surjective; without `import Problems.<p>.Defs`
        # which transitively imports Mathlib, runFrontend fails).
        problem = goal["problem"]
        result = []
        for sg in subgoals:
            slug = sg["slug"]
            statement = sg.get("statement", "")
            fname = f"{slug}.lean"
            staging_path = staging / fname
            staging_path.write_text(
                f"import Problems.{problem}.Defs\n"
                f"-- {statement}\n"
                f"theorem {slug} : {statement} := by\n  sorry\n",
                encoding="utf-8",
            )
            result.append({
                **sg,
                "staging_path": str(staging_path),
                "lean_path": str(subgoals_dir / fname),
            })
        return result

    # ------------------------------------------------------------------
    # Stage: validator
    # ------------------------------------------------------------------

    def _validate(self, goal: dict, subgoals: list[dict]) -> list:
        # Pre-commit phase: sub-goals have no DB id yet; use slug as identifier.
        # validator.check_hyp_carry uses it only as a dict key + error-message
        # interpolation, which accepts strings.
        # P6.x patch 29: pass `statement` so validate() takes the batch hyp_carry
        # path (one runFrontend amortizing Mathlib load instead of N+1 cold loads).
        validator_sgs = [
            {
                "id": sg["slug"],
                "slug": sg["slug"],
                "lean_path": sg["staging_path"],
                "statement": sg.get("statement", ""),
            }
            for sg in subgoals
        ]
        return validate(
            conn=self.conn,
            problem=goal["problem"],
            parent_lean_path=goal["lean_path"],
            subgoals=validator_sgs,
            lake_cwd=self.config.lake_cwd,
            parent_slug=goal["slug"],
            parent_statement=goal.get("question") or "",
        )

    # ------------------------------------------------------------------
    # Stage: self_verify (per-file)
    #
    # Spec calls this "multi mode" (lake build over staging dir for cross-file
    # imports). P2 retains per-file because demo theorems have no inter-sub-
    # goal imports; P3 should switch to a true multi-file lake build via a
    # new Tooling.lake API (see module docstring upgrade points).
    # ------------------------------------------------------------------

    def _self_verify_per_file(
        self, subgoals: list[dict]
    ) -> tuple[bool, list[dict]]:
        """Run lake on each staging file. Sub-goal PASSes iff lake's only
        non-OK message kind is 'hasSorry' (sorry stubs are expected) and the
        run did not time out. Any other message kind ('error', 'warning'),
        or a timeout, fails the sub-goal.

        Returns (all_pass, augmented_subgoals).
        Caller retries the agent stage when all_pass is False.
        """
        augmented: list[dict] = []
        all_pass = True
        for sg in subgoals:
            result = run_lean(
                sg["staging_path"],
                self.config.lake_cwd,
                self.config.lean_timeout,
            )
            non_sorry_msgs = [
                m for m in result.messages if m.get("kind") != "hasSorry"
            ]
            passed = (not result.timed_out) and (not non_sorry_msgs)
            if not passed:
                all_pass = False
            augmented.append({
                **sg,
                "lake_result": result,
                "self_verify_pass": passed,
            })
        return all_pass, augmented

    # ------------------------------------------------------------------
    # Stage: commit (batch TX)
    #
    # 3-step protocol per sub-goal goal + strategy:
    #   Step 1 (begin_batch) — INSERT strategy + goals + strategy_subgoals
    #                          (junction via junction_ops_factory) all in one TX
    #   Step 2 (stage_file)  — mv each staging .lean → lean_path
    #   Step 3 (finalize)    — set commit_state='live'
    #
    # All Step-1 inserts (incl. junction) are atomic per begin_batch's single
    # TX. recover_scan handles cascade cleanup of junction rows when a pending
    # strategy/goal is DELETE'd in INSERT-rollback path.
    # ------------------------------------------------------------------

    def _commit(
        self,
        goal: dict,
        subgoals: list[dict],
        pipeline_id: str,
        staging_dir: str,
    ) -> tuple[int, list[int]]:
        writer = CommitWriter(self.conn)
        problem = goal["problem"]
        goal_id = goal["id"]
        goal_slug = goal["slug"]

        strategy_fname = f"backward_{pipeline_id}.lean"
        strategy_staging = str(Path(staging_dir) / strategy_fname)
        strategy_lean_path = str(
            Path(self.config.base_dir)
            / "Problems" / problem
            / "Goals" / f"{goal_id}_{goal_slug}"
            / strategy_fname
        )

        # Write strategy stub to staging before Step 1 (file must exist for stage_file)
        Path(strategy_staging).parent.mkdir(parents=True, exist_ok=True)
        Path(strategy_staging).write_text(
            f"-- Backward strategy for {goal_slug}\n-- pipeline_id: {pipeline_id}\n",
            encoding="utf-8",
        )

        # P3 C23 IH-trap signal: token Jaccard between parent statement and
        # each sub-goal statement; max → strategies.parent_subgoal_max_similarity.
        # P7 Strategist consumes this; P3 only stores it.
        parent_statement = goal.get("question") or ""
        sg_statements = [sg.get("statement", "") for sg in subgoals]
        ih_sim = parent_subgoal_max_similarity(parent_statement, sg_statements)

        # Step 1: begin_batch — INSERT strategy + all subgoal goals (main ops)
        # + INSERT strategy_subgoals junction rows (junction_ops_factory)
        # ALL atomic in one TX.
        ops: list[dict[str, Any]] = [
            {
                "table": "strategies",
                "op": "insert",
                "data": {
                    "goal_id": goal_id,
                    "lean_path": strategy_lean_path,
                    "status": "proposed",
                    "created_by": pipeline_id,
                    "parent_subgoal_max_similarity": ih_sim,
                },
            }
        ]
        for sg in subgoals:
            # P3 C23 完全取代 P2 statement_hash code; column left NULL for
            # backward-origin sub-goals. dedupe.lean isDefEq is the new
            # uniqueness contract (impl §7.1).
            ops.append({
                "table": "goals",
                "op": "insert",
                "data": {
                    "problem": problem,
                    "slug": sg["slug"],
                    "lean_path": sg["lean_path"],
                    "origin": "backward",
                    "kind": "theorem",
                    "status": "open",
                    "depth": (goal.get("depth") or 0) + 1,
                    "question": sg.get("statement", ""),
                },
            })

        def _make_junction_ops(ids: list[int]) -> list[dict[str, Any]]:
            strat_id = ids[0]
            sg_ids = ids[1:]
            return [
                {
                    "table": "strategy_subgoals",
                    "op": "insert",
                    "data": {
                        "strategy_id": strat_id,
                        "subgoal_id": sg_id,
                        "position": pos,
                    },
                }
                for pos, sg_id in enumerate(sg_ids)
            ]

        ids = writer.begin_batch(ops, junction_ops_factory=_make_junction_ops)
        strategy_id = ids[0]
        subgoal_ids = ids[1:]

        # Step 2: stage_file — mv staging → lean_path
        for sg in subgoals:
            Path(sg["lean_path"]).parent.mkdir(parents=True, exist_ok=True)
            writer.stage_file(sg["staging_path"], sg["lean_path"])
        Path(strategy_lean_path).parent.mkdir(parents=True, exist_ok=True)
        writer.stage_file(strategy_staging, strategy_lean_path)

        # Step 3: finalize — commit_state → 'live'
        for sg_id in subgoal_ids:
            writer.finalize("goals", sg_id, {})
        writer.finalize("strategies", strategy_id, {})

        return strategy_id, subgoal_ids

    # ------------------------------------------------------------------
    # Pipeline lifecycle (parity with builder.py)
    # ------------------------------------------------------------------

    def _insert_pipeline(
        self, pipeline_id: str, goal_id: int, session_id: str
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "session_id, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pipeline_id, "Backward", "atomic",
                    str(goal_id), "Goal", "running",
                    session_id, _now(),
                ),
            )

    def _finish_pipeline(self, pipeline_id: str, outcome: str) -> None:
        # outcome ∈ {success, exhausted, unproductive}
        # success → succeeded; exhausted/unproductive → failed
        status = "succeeded" if outcome == "success" else "failed"
        with self.conn:
            self.conn.execute(
                "UPDATE pipelines SET status = ?, outcome = ?, "
                "finished_at = ? WHERE id = ?",
                (status, outcome, _now(), pipeline_id),
            )

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def run(self, goal_id: int) -> BackwardResult:
        """Run the full Backward stage sequence for the given goal.

        Test hooks (mutually exclusive — see docs/dev/test_hooks.md):
          BACKWARD_MOCK=success_leaf   → bypass agent, write a trivial leaf
                                          strategy with `theorem ... := by
                                          sorry` (Builder + LAKE_MOCK=proved
                                          closes it end-to-end). Used by P2
                                          acceptance #0.
          BACKWARD_FORCE=exhausted     → return exhausted immediately
          BACKWARD_FORCE=unproductive  → return unproductive immediately
          BACKWARD_FORCE=succeed       → return success with no strategy_id
                                          (test fixtures own the rows; used
                                          by P3 acceptance #6a generic-N=5
                                          trigger tests)

        Naming convention (test_hooks.md §規則): `*_MOCK=spec` replaces real
        behavior; `*_FORCE=value` forces a specific outcome. Splitting these
        avoids C18/P3 collision (P3 plans BACKWARD_FORCE for failure-path
        coverage tests).
        """
        mock = os.environ.get("BACKWARD_MOCK")
        if mock == "success_leaf":
            return self._mock_success_leaf(goal_id)
        if mock is not None:
            raise ValueError(
                f"unknown BACKWARD_MOCK value: {mock!r}; "
                "valid: 'success_leaf'. For outcome forcing, use BACKWARD_FORCE."
            )

        force = os.environ.get("BACKWARD_FORCE")
        if force == "exhausted":
            return BackwardResult(outcome="exhausted")
        if force == "unproductive":
            return BackwardResult(outcome="unproductive")
        if force == "succeed":
            # P3 C26: minimal success-shell. No strategy_id / subgoal_ids
            # written — fixture / test seeds those rows when relevant.
            # (Contrast BACKWARD_MOCK=success_leaf which DOES write a stub
            #  strategy + .lean file end-to-end.)
            return BackwardResult(outcome="success")
        if force is not None:
            raise ValueError(
                f"unknown BACKWARD_FORCE value: {force!r}; "
                "valid: 'exhausted' | 'unproductive' | 'succeed'."
            )

        try:
            goal = _row_as_dict(self.conn, "goals", goal_id)
        except ValueError:
            return BackwardResult(outcome="exhausted")

        pipeline_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        staging_dir = str(
            Path(self.config.base_dir)
            / "Problems" / goal["problem"]
            / "Goals" / f"{goal_id}_{goal['slug']}"
            / "Staging" / session_id
        )

        self._insert_pipeline(pipeline_id, goal_id, session_id)

        dead_attempts = self.failure_replay(goal_id)
        candidate_lemmas = self.find_lemmas(goal)
        self.find_subgoals(goal)

        result = self._run_loop(
            goal, pipeline_id, session_id, staging_dir,
            dead_attempts, candidate_lemmas,
        )
        self._finish_pipeline(pipeline_id, result.outcome)
        return result

    def _mock_success_leaf(self, goal_id: int) -> BackwardResult:
        """Test-only (BACKWARD_MOCK=success_leaf): write trivial leaf strategy.

        Insert a strategies row pointing to a stub .lean file containing
        `theorem <slug> : <question> := by sorry`. No sub-goals. Builder runs
        next; with LAKE_MOCK=proved it closes the proof end-to-end. Used by
        P2 acceptance #0 demo subprocess test.
        """
        try:
            goal = _row_as_dict(self.conn, "goals", goal_id)
        except ValueError:
            return BackwardResult(outcome="exhausted")

        pipeline_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        self._insert_pipeline(pipeline_id, goal_id, session_id)

        problem = goal["problem"]
        goal_slug = goal["slug"]
        statement = goal.get("question") or "True"
        strategy_lean_path = str(
            Path(self.config.base_dir)
            / "Problems" / problem
            / "Goals" / f"{goal_id}_{goal_slug}"
            / f"backward_mock_{pipeline_id[:8]}.lean"
        )
        Path(strategy_lean_path).parent.mkdir(parents=True, exist_ok=True)
        Path(strategy_lean_path).write_text(
            f"import Problems.{problem}.Defs\n\n"
            f"theorem {goal_slug} : {statement} := by sorry\n",
            encoding="utf-8",
        )

        writer = CommitWriter(self.conn)
        strategy_id = writer.begin("strategies", "insert", {
            "goal_id": goal_id,
            "lean_path": strategy_lean_path,
            "status": "proposed",
            "created_by": pipeline_id,
        })
        writer.finalize("strategies", strategy_id, {})

        self._finish_pipeline(pipeline_id, "success")
        return BackwardResult(
            outcome="success", strategy_id=strategy_id, subgoal_ids=[],
        )

    def _run_loop(
        self,
        goal: dict,
        pipeline_id: str,
        session_id: str,
        staging_dir: str,
        dead_attempts: list[dict],
        candidate_lemmas: list[dict] | None = None,
    ) -> BackwardResult:
        # P6.x patch 10: per-stage observability. Every retry exit path emits
        # a 'cascade' event so operators can see why Backward exhausted (was
        # it parse fail / dedupe collapse / validator / self_verify?).
        for _attempt in range(self.config.max_retries):
            # Fresh staging dir each retry — avoid cross-attempt leftover files
            # confusing validator/self_verify on a different sub-goal slug set.
            shutil.rmtree(staging_dir, ignore_errors=True)
            Path(staging_dir).mkdir(parents=True, exist_ok=True)

            # P6.x patch 11: claude CLI rejects reused --session-id with
            # "already in use". Mint a fresh UUID per retry. The
            # pipeline-level session_id (stored in pipelines.session_id)
            # remains the original for cross-retry traceability.
            retry_session_id = str(uuid.uuid4()) if _attempt > 0 else session_id
            response = self._run_agent(goal, dead_attempts, retry_session_id,
                                       staging_dir, candidate_lemmas)
            if response is None:
                self._emit_stage_fail(goal, pipeline_id, _attempt,
                                      "agent_no_response")
                return BackwardResult(outcome="exhausted")

            proposal = self._parse_proposal(response.output, goal=goal)
            if proposal is None:
                self._emit_stage_fail(goal, pipeline_id, _attempt,
                                      "parse_proposal_fail",
                                      detail=(response.output[:300]
                                              if response.output else ""))
                continue

            # P6.x patch 3: Leaf path — agent claims goal is directly
            # provable by a single tactic block. Skip decomposition,
            # write a leaf strategy, commit with empty subgoals so BFS
            # treats it as ready for Builder verification.
            if proposal.get("combinator") == "Leaf":
                strategy_id = self._commit_leaf(
                    goal, proposal["proof"], pipeline_id, staging_dir,
                )
                return BackwardResult(
                    outcome="success",
                    strategy_id=strategy_id,
                    subgoal_ids=[],
                )

            subgoals_raw = proposal.get("subgoals", [])
            if not subgoals_raw:
                self._emit_stage_fail(goal, pipeline_id, _attempt,
                                      "subgoals_empty")
                return BackwardResult(outcome="unproductive")

            subgoals = self._dedupe(subgoals_raw, staging_dir, goal)
            if not subgoals:
                self._emit_stage_fail(goal, pipeline_id, _attempt,
                                      "dedupe_collapsed",
                                      detail=f"all {len(subgoals_raw)} dedupe'd")
                return BackwardResult(outcome="unproductive")

            subgoals = self._write_staging_files(subgoals, staging_dir, goal)

            errors = self._validate(goal, subgoals)
            if errors:
                self._emit_stage_fail(goal, pipeline_id, _attempt,
                                      "validator_fail",
                                      detail=f"{len(errors)} errors: "
                                             + "; ".join(
                                                 f"{e.check}={e.detail}"
                                                 for e in errors[:3]
                                             ))
                continue

            all_pass, subgoals = self._self_verify_per_file(subgoals)
            if not all_pass:
                self._emit_stage_fail(goal, pipeline_id, _attempt,
                                      "self_verify_fail")
                # pipelines.md §2 stage 7 [fail → retry from step 4]
                continue

            strategy_id, subgoal_ids = self._commit(
                goal, subgoals, pipeline_id, staging_dir
            )
            return BackwardResult(
                outcome="success",
                strategy_id=strategy_id,
                subgoal_ids=subgoal_ids,
            )

        self._emit_stage_fail(goal, pipeline_id, self.config.max_retries,
                              "max_retries_exhausted")
        return BackwardResult(outcome="exhausted")

    def _commit_leaf(
        self,
        goal: dict,
        proof: str,
        pipeline_id: str,
        staging_dir: str,
    ) -> int:
        """P6.x patch 3 + 22: commit a leaf-path strategy.

        Writes the agent's proof to a SEPARATE strategy file (sibling of
        the goal file in the same directory) with a strategy-specific
        namespace. The goal file is never touched — it stays at the
        original `:= by sorry` template until promotion.

        This avoids two concrete bugs that the inline-overwrite approach
        had:
          1. **Race vs Builder**: Builder runs `lake env lean <file>`
             possibly concurrently with cascade post-checks. If post-
             check rolls back the goal file, an in-flight Builder reads
             a partial state.
          2. **Rollback on forbidden_lemmas / accept-rule rejection**:
             Restoring the `:= by sorry` template after a failed
             post-verify is a destructive write that races with anything
             else reading the goal file (proved.lean, sibling strategy
             files, BFS).

        Architecture: strategy file declares the theorem under its own
        namespace `Problems.<p>.Goals.<id_seg>._strategy_<pid_short>`,
        so it never collides with the goal-file namespace. promote_to_library
        re-exports from the strategy module after all checks pass.
        """
        writer = CommitWriter(self.conn)
        goal_id = goal["id"]
        goal_slug = goal["slug"]
        statement = goal.get("question") or ""
        problem = goal["problem"]

        # Strategy-specific namespace — different from the goal-file
        # namespace, so the strategy file never collides with the goal
        # file when both live in the same directory.
        id_segment = f"{goal_id}_{goal_slug}"
        if id_segment[:1].isdigit():
            id_segment_lean = f"«{id_segment}»"
        else:
            id_segment_lean = id_segment
        pid_short = pipeline_id.replace("-", "_")[:16]
        strategy_module_segment = f"_strategy_{pid_short}"
        ns = (
            f"Problems.{problem}.Goals."
            f"{id_segment_lean}.{strategy_module_segment}"
        )

        proven_content = (
            f"import Problems.{problem}.Defs\n\n"
            f"namespace {ns}\n\n"
            f"theorem {goal_slug} : {statement} := {proof}\n\n"
            f"end {ns}\n"
        )

        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        leaf_staging = str(
            Path(staging_dir) / f"{strategy_module_segment}.lean"
        )
        Path(leaf_staging).write_text(proven_content, encoding="utf-8")

        # Strategy file lives in the goal directory (a sibling of the
        # goal file). Same parent dir so the module hierarchy lines up.
        goal_dir = Path(self.config.base_dir) / Path(
            goal["lean_path"]
        ).parent
        strategy_lean_path = str(goal_dir / f"{strategy_module_segment}.lean")

        ops = [{
            "table": "strategies",
            "op": "insert",
            "data": {
                "goal_id": goal_id,
                "lean_path": strategy_lean_path,
                "status": "proposed",
                "created_by": pipeline_id,
                "parent_subgoal_max_similarity": 0.0,
            },
        }]
        ids = writer.begin_batch(ops)
        strategy_id = ids[0]

        goal_dir.mkdir(parents=True, exist_ok=True)
        writer.stage_file(leaf_staging, strategy_lean_path)
        writer.finalize("strategies", strategy_id, {})

        # P7 演習 fix: do NOT enqueue Builder here. The scheduler's
        # _cascade_backward (success branch) already enqueues a Builder
        # task for leaf strategies (no sub-goals), reachable from both
        # daemon and --once paths. Inline-enqueueing here in addition
        # produces TWO queue rows for the same strategy, both of which
        # spawn before the BFS retry-ceiling guard sees any pipeline
        # row → two Builder threads run on the same staging file
        # simultaneously and one always wins the cascade race. Dropping
        # this duplicate makes leaf success path clean: Backward writes
        # strategy + commits, returns success; cascade decides spawn.

        return strategy_id

    def _emit_stage_fail(
        self,
        goal: dict,
        pipeline_id: str,
        attempt: int,
        stage: str,
        detail: str = "",
    ) -> None:
        """P6.x patch 10: emit a 'cascade' event row so operators can
        diagnose Backward exhaustion mode without code instrumentation.
        Best-effort: SQL fail does not propagate (event log is observable
        side-channel, not part of the Backward outcome contract)."""
        import json as _json
        try:
            payload = _json.dumps({
                "rule": "backward_stage_fail",
                "pipeline_id": pipeline_id,
                "goal_id": goal.get("id"),
                "attempt": attempt,
                "stage": stage,
                "detail": detail,
            })
            with self.conn:
                self.conn.execute(
                    "INSERT INTO events (kind, payload, ts) VALUES "
                    "(?, ?, ?)",
                    ("cascade", payload, _now()),
                )
        except sqlite3.Error:
            pass
