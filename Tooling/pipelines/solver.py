"""Solver pipeline (P7 演習 refactor 路線 1).

The 1-shot direct-proof attempt that used to live inside `Backward` as
"Path A leaf". Pulled out into its own pipeline so Backward becomes
purely about decomposition. Workflow:

  goal → BFS → Solver (1-shot direct attempt)
       ├─ success → strategy committed (no sub-goals) → Builder verifies
       └─ failure → Backward (decomposition) → sub-goals attacked recursively

Stages:
  1. failure_replay (read goal-scoped Solver dead_attempts)
  2. agent (LLM proposes a single tactic block / direct proof body)
  3. self_verify (lake build the staging file; sorry stub OK iff proof
     itself uses sorry — typically NOT the case for Solver)
  4. commit (write strategy file in sibling slot, INSERT strategies row;
     scheduler cascade enqueues Builder)

Outcome enum:
  success   — strategy committed; cascade fires Builder
  exhausted — agent unable to produce a verifiable proof within retries

The strategy this pipeline produces is structurally a "leaf strategy"
(no sub-goal links in strategy_subgoals). Builder verifies the proof
body inline; on success cascade marks goal proved + finalizes goal
file (existing _finalize_goal_file_from_strategy).

Test hooks:
  SOLVER_FORCE=exhausted | success_trivial — bypass agent for tests.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Tooling.commit import CommitWriter
from Tooling.lake import run_lean
from Tooling.stages.failure_replay import failure_replay as _stage_failure_replay
from Tooling.agent.provider import AgentResponse, FallbackChain, ModelResolver


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_as_dict(conn: sqlite3.Connection, table: str, row_id: int) -> dict:
    cur = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"{table} row {row_id} not found")
    return dict(zip([d[0] for d in cur.description], row))


@dataclass
class SolverConfig:
    base_dir: str
    lake_cwd: str
    max_retries: int = 3
    lean_timeout: float = 600.0


@dataclass
class SolverResult:
    outcome: str            # 'success' | 'exhausted'
    strategy_id: int | None = None


class Solver:
    def __init__(
        self,
        conn: sqlite3.Connection,
        chain: FallbackChain,
        config: SolverConfig,
        resolver: ModelResolver | None = None,
    ) -> None:
        self.conn = conn
        self.chain = chain
        self.config = config
        self.resolver = resolver or ModelResolver()

    # ------------------------------------------------------------------
    # Stage 1: failure_replay
    # ------------------------------------------------------------------

    def failure_replay(self, goal_id: int) -> list[dict]:
        return _stage_failure_replay(self.conn, goal_id, "Goal")

    # ------------------------------------------------------------------
    # Stage 2: agent
    # ------------------------------------------------------------------

    def _load_prompt(self) -> str:
        p = Path(__file__).parents[2] / "docs" / "prompts" / "solver.md"
        return p.read_text(encoding="utf-8")

    def _build_prompt(self, goal: dict, dead_attempts: list[dict]) -> str:
        template = self._load_prompt()
        dead_str = (
            json.dumps(dead_attempts, indent=2) if dead_attempts else "[]"
        )
        return (
            template
            .replace("{{GOAL_PROBLEM}}", goal.get("problem") or "")
            .replace("{{GOAL_SLUG}}", goal.get("slug") or "")
            .replace("{{GOAL_STATEMENT}}", goal.get("question") or "")
            .replace("{{DEAD_ATTEMPTS}}", dead_str)
        )

    def _run_agent(
        self, prompt: str, session_id: str, staging_dir: str,
    ) -> AgentResponse | None:
        tier = self.resolver.resolve("solver", "agent")
        response, outcome = self.chain.run(
            model_tier=tier, prompt=prompt,
            scope_dirs=[staging_dir], session_id=session_id,
            staging_dir=staging_dir,
        )
        return response if outcome == "success" else None

    def _parse_proof(self, output: str) -> str | None:
        """Extract the proof body from agent output.

        Output schema (simple):
            ```json
            {"proof": "by <tactic_block>"}
            ```
        Reject non-JSON, missing/empty proof, non-string proof.
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
        proof = obj.get("proof")
        if not isinstance(proof, str) or not proof.strip():
            return None
        return proof

    # ------------------------------------------------------------------
    # Stage 3: self_verify (lake build of staging file with the proof)
    # ------------------------------------------------------------------

    def _write_staging(
        self, goal: dict, proof: str, pipeline_id: str, staging_dir: str,
    ) -> tuple[str, str]:
        """Write the candidate strategy file.

        Returns (staging_path, canonical_strategy_path) — staging_path is
        what we lake-build for self_verify; canonical_strategy_path is
        where commit will move it.
        """
        goal_id = goal["id"]
        goal_slug = goal["slug"]
        statement = goal.get("question") or ""
        problem = goal["problem"]

        id_segment = f"{goal_id}_{goal_slug}"
        id_segment_lean = (f"«{id_segment}»"
                           if id_segment[:1].isdigit() else id_segment)
        pid_short = pipeline_id.replace("-", "_")[:16]
        strategy_module_segment = f"_strategy_{pid_short}"
        ns = (
            f"Problems.{problem}.Goals."
            f"{id_segment_lean}.{strategy_module_segment}"
        )
        content = (
            f"import Problems.{problem}.Defs\n\n"
            f"namespace {ns}\n\n"
            f"theorem {goal_slug} : {statement} := {proof}\n\n"
            f"end {ns}\n"
        )

        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        staging_path = str(
            Path(staging_dir) / f"{strategy_module_segment}.lean"
        )
        Path(staging_path).write_text(content, encoding="utf-8")

        goal_dir = Path(self.config.base_dir) / Path(goal["lean_path"]).parent
        canonical = str(goal_dir / f"{strategy_module_segment}.lean")
        return staging_path, canonical

    def _self_verify(self, staging_path: str) -> bool:
        """Run lake on the staging file. Pass iff no non-sorry messages
        and not timed out. (Solver proofs typically have NO sorry —
        Solver only succeeds when LLM produces a real proof body.)"""
        result = run_lean(
            staging_path, self.config.lake_cwd, self.config.lean_timeout,
        )
        non_sorry = [
            m for m in result.messages if m.get("kind") != "hasSorry"
        ]
        return (not result.timed_out) and (not non_sorry)

    # ------------------------------------------------------------------
    # Stage 4: commit (INSERT strategies row, atomic stage_file)
    # ------------------------------------------------------------------

    def _commit(
        self,
        goal: dict,
        staging_path: str,
        canonical_path: str,
        pipeline_id: str,
    ) -> int:
        writer = CommitWriter(self.conn)
        # Path lean_path stored relative to base_dir for portability.
        rel = Path(canonical_path).relative_to(self.config.base_dir).as_posix() \
            if Path(canonical_path).is_absolute() and \
                Path(canonical_path).is_relative_to(self.config.base_dir) \
            else canonical_path
        ops = [{
            "table": "strategies",
            "op": "insert",
            "data": {
                "goal_id": goal["id"],
                "lean_path": rel,
                "status": "proposed",
                "created_by": pipeline_id,
                "parent_subgoal_max_similarity": 0.0,
            },
        }]
        ids = writer.begin_batch(ops)
        strategy_id = ids[0]
        Path(canonical_path).parent.mkdir(parents=True, exist_ok=True)
        writer.stage_file(staging_path, canonical_path)
        writer.finalize("strategies", strategy_id, {})
        return strategy_id

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------

    def _insert_pipeline(
        self, pipeline_id: str, goal_id: int, session_id: str,
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "session_id, started_at) VALUES "
                "(?, 'Solver', 'atomic', ?, 'Goal', 'running', ?, ?)",
                (pipeline_id, str(goal_id), session_id, _now()),
            )

    def _finish_pipeline(self, pipeline_id: str, outcome: str) -> None:
        status = "succeeded" if outcome == "success" else "failed"
        with self.conn:
            self.conn.execute(
                "UPDATE pipelines SET status = ?, outcome = ?, "
                "finished_at = ? WHERE id = ?",
                (status, outcome, _now(), pipeline_id),
            )

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def run(self, goal_id: int) -> SolverResult:
        force = os.environ.get("SOLVER_FORCE")
        if force == "exhausted":
            return SolverResult(outcome="exhausted")
        if force is not None and force != "exhausted":
            raise ValueError(
                f"unknown SOLVER_FORCE: {force!r}; valid: 'exhausted'."
            )

        try:
            goal = _row_as_dict(self.conn, "goals", goal_id)
        except ValueError:
            return SolverResult(outcome="exhausted")

        pipeline_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        staging_dir = str(
            Path(self.config.base_dir)
            / "Problems" / goal["problem"]
            / "Goals" / f"{goal_id}_{goal['slug']}"
            / "_SolverStaging" / session_id
        )
        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        self._insert_pipeline(pipeline_id, goal_id, session_id)

        dead_attempts = self.failure_replay(goal_id)
        prompt = self._build_prompt(goal, dead_attempts)

        for attempt in range(self.config.max_retries):
            retry_session_id = (
                str(uuid.uuid4()) if attempt > 0 else session_id
            )
            response = self._run_agent(prompt, retry_session_id, staging_dir)
            if response is None:
                continue
            proof = self._parse_proof(response.output)
            if proof is None:
                continue
            staging_path, canonical_path = self._write_staging(
                goal, proof, pipeline_id, staging_dir,
            )
            if not self._self_verify(staging_path):
                continue
            strategy_id = self._commit(
                goal, staging_path, canonical_path, pipeline_id,
            )
            self._finish_pipeline(pipeline_id, "success")
            return SolverResult(outcome="success", strategy_id=strategy_id)

        self._finish_pipeline(pipeline_id, "exhausted")
        return SolverResult(outcome="exhausted")
