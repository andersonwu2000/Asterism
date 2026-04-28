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

import hashlib
import json
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
from Tooling.stages.validator import validate
from Tooling.agent.provider import AgentResponse, FallbackChain, ModelResolver


_VALID_COMBINATORS: frozenset[str] = frozenset({"And", "Or", "Exists"})


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
    # Stage: failure_replay (P2 stub — returns empty)
    # ------------------------------------------------------------------

    def failure_replay(self, pipeline_id: str) -> list[dict]:
        return []

    # ------------------------------------------------------------------
    # Stage: find_lemmas (P2 stub — returns empty)
    # ------------------------------------------------------------------

    def find_lemmas(self, goal: dict) -> list[str]:
        return []

    # ------------------------------------------------------------------
    # Stage: find_subgoals (P2 stub — returns empty)
    # ------------------------------------------------------------------

    def find_subgoals(self, goal: dict) -> list[dict]:
        return []

    # ------------------------------------------------------------------
    # Stage: agent
    # ------------------------------------------------------------------

    def _load_prompt_template(self) -> str:
        prompt_path = Path(__file__).parents[2] / "docs" / "prompts" / "backward.md"
        return prompt_path.read_text(encoding="utf-8")

    def _build_prompt(self, goal: dict, dead_attempts: list[dict]) -> str:
        template = self._load_prompt_template()
        dead_str = json.dumps(dead_attempts, indent=2) if dead_attempts else "[]"
        return (
            template
            .replace("{{GOAL_PROBLEM}}", goal.get("problem") or "")
            .replace("{{GOAL_SLUG}}", goal.get("slug") or "")
            .replace("{{GOAL_STATEMENT}}", goal.get("question") or "")
            .replace("{{DEAD_ATTEMPTS}}", dead_str)
        )

    def _run_agent(
        self,
        goal: dict,
        dead_attempts: list[dict],
        session_id: str,
        staging_dir: str,
    ) -> AgentResponse | None:
        model_tier = self.resolver.resolve("backward", "agent")
        prompt = self._build_prompt(goal, dead_attempts)
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

    def _parse_proposal(self, output: str) -> dict | None:
        """Extract + schema-validate PROPOSAL from agent output.

        Requires a ```json ... ``` code block as specified in backward.md.
        Returns None (→ caller retries) if any of:
          - no JSON code block / malformed JSON
          - top-level not a dict
          - combinator not in {And, Or, Exists}
          - subgoals not a list
          - any sub-goal not a dict, or missing non-empty 'slug' / 'statement'
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
    # Stage: dedupe (local) — statement_hash SHA256
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_hash(statement: str) -> str:
        normalized = re.sub(r'\s+', ' ', statement.strip())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _dedupe(self, subgoals: list[dict]) -> list[dict]:
        """Remove subgoals duplicating either an existing goal (DB lookup) or
        a previously-seen sub-goal in the same proposal."""
        seen_hashes: set[str] = set()
        unique: list[dict] = []
        for sg in subgoals:
            h = self._normalize_hash(sg.get("statement", ""))
            if h in seen_hashes:
                continue
            row = self.conn.execute(
                "SELECT id FROM goals WHERE statement_hash = ?", (h,)
            ).fetchone()
            if row is None:
                seen_hashes.add(h)
                unique.append({**sg, "statement_hash": h})
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
        result = []
        for sg in subgoals:
            slug = sg["slug"]
            statement = sg.get("statement", "")
            fname = f"{slug}.lean"
            staging_path = staging / fname
            staging_path.write_text(
                f"-- {statement}\ntheorem {slug} : {statement} := by\n  sorry\n",
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
        validator_sgs = [
            {
                "id": sg["slug"],
                "slug": sg["slug"],
                "lean_path": sg["staging_path"],
            }
            for sg in subgoals
        ]
        return validate(
            conn=self.conn,
            problem=goal["problem"],
            parent_lean_path=goal["lean_path"],
            subgoals=validator_sgs,
            lake_cwd=self.config.lake_cwd,
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
                },
            }
        ]
        for sg in subgoals:
            ops.append({
                "table": "goals",
                "op": "insert",
                "data": {
                    "problem": problem,
                    "slug": sg["slug"],
                    "lean_path": sg["lean_path"],
                    "statement_hash": sg["statement_hash"],
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
        """Run the full Backward stage sequence for the given goal."""
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

        dead_attempts = self.failure_replay(pipeline_id)
        self.find_lemmas(goal)
        self.find_subgoals(goal)

        result = self._run_loop(goal, pipeline_id, session_id, staging_dir, dead_attempts)
        self._finish_pipeline(pipeline_id, result.outcome)
        return result

    def _run_loop(
        self,
        goal: dict,
        pipeline_id: str,
        session_id: str,
        staging_dir: str,
        dead_attempts: list[dict],
    ) -> BackwardResult:
        for _attempt in range(self.config.max_retries):
            # Fresh staging dir each retry — avoid cross-attempt leftover files
            # confusing validator/self_verify on a different sub-goal slug set.
            shutil.rmtree(staging_dir, ignore_errors=True)
            Path(staging_dir).mkdir(parents=True, exist_ok=True)

            response = self._run_agent(goal, dead_attempts, session_id, staging_dir)
            if response is None:
                return BackwardResult(outcome="exhausted")

            proposal = self._parse_proposal(response.output)
            if proposal is None:
                continue

            subgoals_raw = proposal.get("subgoals", [])
            if not subgoals_raw:
                return BackwardResult(outcome="unproductive")

            subgoals = self._dedupe(subgoals_raw)
            if not subgoals:
                return BackwardResult(outcome="unproductive")

            subgoals = self._write_staging_files(subgoals, staging_dir, goal)

            errors = self._validate(goal, subgoals)
            if errors:
                continue

            all_pass, subgoals = self._self_verify_per_file(subgoals)
            if not all_pass:
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

        return BackwardResult(outcome="exhausted")
