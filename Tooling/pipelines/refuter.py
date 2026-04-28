"""Refuter pipeline runtime (P4 C29).

Builds ¬G as a new Goal so that Builder/Backward can attack it. Refuter does
NOT prove ¬G itself — it only writes the negation statement and inserts the
Goal with bidirectional ``twin_of`` linkage. When Builder later proves ¬G,
the cascade table (P4 C30) flips G to ``status='refuted'``.

Stage sequence (architecture_pipelines.md §3):
  failure_replay → agent → self_verify → dedupe (local) → commit

The agent reads ``G.evidence.counterexample_witness`` if present, allowing a
witness-based short proof template. P4 cycle plan defers Counterexample, so
the witness slot is reserved (always empty for now); the generic ¬G classical
path is the active code.

Public API:
  Refuter(conn, chain, config, resolver=None)
  Refuter.run(goal_id) -> RefuterResult
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Tooling.commit import CommitWriter
from Tooling.lake import run_lean
from Tooling.stages.failure_replay import failure_replay as _stage_failure_replay
from Tooling.subsystems.dedupe import dedupe as _stage_dedupe
from Tooling.agent.provider import AgentResponse, FallbackChain, ModelResolver


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_as_dict(conn: sqlite3.Connection, table: str, row_id: int) -> dict[str, Any]:
    cur = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"{table} row {row_id} not found")
    return dict(zip([d[0] for d in cur.description], row))


@dataclass
class RefuterConfig:
    base_dir: str
    lake_cwd: str
    max_retries: int = 3
    lean_timeout: float = 600.0


@dataclass
class RefuterResult:
    outcome: str            # "success" | "exhausted"
    negation_goal_id: int | None = None
    deduped: bool = False   # True when commit reused an existing ¬G


class Refuter:
    def __init__(
        self,
        conn: sqlite3.Connection,
        chain: FallbackChain,
        config: RefuterConfig,
        resolver: ModelResolver | None = None,
    ) -> None:
        self.conn = conn
        self.chain = chain
        self.config = config
        self.resolver = resolver or ModelResolver()

    # ------------------------------------------------------------------
    # Stage: failure_replay
    # ------------------------------------------------------------------

    def failure_replay(self, goal_id: int) -> list[dict]:
        return _stage_failure_replay(self.conn, goal_id, "Goal")

    # ------------------------------------------------------------------
    # Stage: agent
    # ------------------------------------------------------------------

    def _load_prompt_template(self) -> str:
        prompt_path = Path(__file__).parents[2] / "docs" / "prompts" / "refuter.md"
        return prompt_path.read_text(encoding="utf-8")

    def _build_prompt(self, goal: dict, dead_attempts: list[dict]) -> str:
        template = self._load_prompt_template()
        dead_str = json.dumps(dead_attempts, indent=2) if dead_attempts else "[]"
        # Witness slot — Counterexample-only payload, deferred. Falls through
        # to the generic ¬G path in the prompt.
        evidence_witness = self._extract_witness_block(goal)
        return (
            template
            .replace("{{GOAL_PROBLEM}}", goal.get("problem") or "")
            .replace("{{GOAL_SLUG}}", goal.get("slug") or "")
            .replace("{{GOAL_STATEMENT}}", goal.get("question") or "")
            .replace("{{DEAD_ATTEMPTS}}", dead_str)
            .replace("{{EVIDENCE_WITNESS}}", evidence_witness)
        )

    def _extract_witness_block(self, goal: dict) -> str:
        """Extract counterexample witness from goals.evidence if present.

        Schema (reserved per D-13-1, populated by Counterexample silver
        commit when that pipeline ships):
          evidence.counterexample_witness = {
              "witness_lean_expr": "<Lean expr>",
              "witness_type":      "<Lean type>",
              "predicate_def":     "<def name>",
          }
        With Counterexample deferred, this branch is dead-but-wired so a
        future Counterexample landing only needs to flip the populator.
        """
        ev_raw = goal.get("evidence")
        if not ev_raw:
            return "(none)"
        try:
            ev = json.loads(ev_raw) if isinstance(ev_raw, str) else ev_raw
        except (json.JSONDecodeError, TypeError):
            return "(none)"
        if not isinstance(ev, dict):
            return "(none)"
        w = ev.get("counterexample_witness")
        if not isinstance(w, dict):
            return "(none)"
        expr = w.get("witness_lean_expr")
        ty = w.get("witness_type")
        pdef = w.get("predicate_def")
        if not expr:
            return "(none)"
        return (
            f"witness_lean_expr: {expr}\n"
            f"witness_type:      {ty or '?'}\n"
            f"predicate_def:     {pdef or '?'}"
        )

    def _run_agent(
        self,
        goal: dict,
        dead_attempts: list[dict],
        session_id: str,
        staging_dir: str,
    ) -> AgentResponse | None:
        model_tier = self.resolver.resolve("refuter", "agent")
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
    # Parse {negation_slug, negation_statement}
    # ------------------------------------------------------------------

    def _parse_negation(self, output: str) -> dict | None:
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', output)
        if not m:
            return None
        try:
            obj = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        slug = obj.get("negation_slug")
        statement = obj.get("negation_statement")
        if not isinstance(slug, str) or not slug:
            return None
        if not isinstance(statement, str) or not statement:
            return None
        return obj

    # ------------------------------------------------------------------
    # Stage: self_verify
    # ------------------------------------------------------------------

    def _write_staging(
        self, negation: dict, staging_dir: str, goal: dict
    ) -> dict:
        staging = Path(staging_dir)
        staging.mkdir(parents=True, exist_ok=True)
        slug = negation["negation_slug"]
        statement = negation["negation_statement"]
        fname = f"{slug}.lean"
        staging_path = staging / fname

        # ¬G is a fresh root; final lean_path under Problems/<p>/Goals/<id_slug>/
        # follows backward's convention: nested under the new Goal's own dir
        # (id is unknown until commit; use slug for staging, real path computed
        # later inside _commit using the post-INSERT id).
        staging_path.write_text(
            f"-- Refuter negation of {goal['slug']}: {goal.get('question', '')}\n"
            f"theorem {slug} : {statement} := by\n  sorry\n",
            encoding="utf-8",
        )
        return {
            "negation_slug": slug,
            "negation_statement": statement,
            "staging_path": str(staging_path),
        }

    def _self_verify(self, neg_file: dict) -> bool:
        """Run lake on the staging ¬G .lean. Pass iff lake's only non-OK
        message is `hasSorry` and it didn't time out (same rule as Backward
        per-file check)."""
        result = run_lean(
            neg_file["staging_path"],
            self.config.lake_cwd,
            self.config.lean_timeout,
        )
        if result.timed_out:
            return False
        non_sorry = [m for m in result.messages if m.get("kind") != "hasSorry"]
        return not non_sorry

    # ------------------------------------------------------------------
    # Stage: dedupe (local)
    # ------------------------------------------------------------------

    def _dedupe_against_existing(
        self, neg_file: dict, goal: dict
    ) -> int | None:
        """Returns existing ¬G goal id if dedupe.lean reports a hit, else None.

        Scope: same Problem only (architecture spec — local dedupe). Cross-
        Problem hits are ignored to keep imports valid in subsequent Builder
        runs on this Problem.
        """
        problem = goal["problem"]
        entry_rows = self.conn.execute(
            "SELECT id, lean_path FROM goals "
            "WHERE commit_state = 'live' AND problem = ?",
            (problem,),
        ).fetchall()
        entries = [{"id": int(r[0]), "lean_path": str(r[1])} for r in entry_rows]
        if not entries:
            return None

        result = _stage_dedupe(
            Path(neg_file["staging_path"]),
            entries,
            conn=self.conn,
            mode="strict",
        )
        if result.outcome == "hit":
            return int(result.entry_id) if result.entry_id is not None else None
        if result.outcome == "timeout":
            # Spec §風險 line 230: NOVEL fallback on timeout. Loud surface
            # to match Backward._dedupe pattern (no silent failure).
            import sys
            print(
                f"[refuter._dedupe] timeout for negation {neg_file['negation_slug']!r}; "
                "treated as novel per spec §風險",
                file=sys.stderr,
            )
        return None

    # ------------------------------------------------------------------
    # Stage: commit (twin-bidirectional)
    # ------------------------------------------------------------------

    def _commit_novel(
        self,
        goal: dict,
        neg_file: dict,
        pipeline_id: str,
    ) -> int:
        """Insert ¬G as new Goal; bidirectional twin_of UPDATE.

        Step 1: begin_batch:
          op[0] insert goals (¬G) with twin_of=G.id  (¬G→G link set at INSERT)
          op[1] update goals (G) — snapshot only, new twin_of comes at finalize
        Step 2: stage_file ¬G staging → final lean_path
        Step 3: finalize ¬G ({}); finalize G ({"twin_of": neg_id})  (G→¬G link)
        """
        writer = CommitWriter(self.conn)
        problem = goal["problem"]
        goal_id = goal["id"]
        slug = neg_file["negation_slug"]
        statement = neg_file["negation_statement"]

        # ¬G's final lean_path: use a slug-keyed dir to avoid the chicken-and-
        # egg of {id}_{slug} (id unknown pre-commit). Other origin paths
        # (refuter_negation specifically) use slug-only dir per spec sample
        # `Problems/<p>/Goals/<slug>.lean` and we adopt a similar layout.
        neg_lean_path = str(
            Path(self.config.base_dir)
            / "Problems" / problem
            / "Goals" / f"{slug}.lean"
        )

        ops: list[dict[str, Any]] = [
            {
                "table": "goals",
                "op": "insert",
                "data": {
                    "problem": problem,
                    "slug": slug,
                    "lean_path": neg_lean_path,
                    "origin": "refuter_negation",
                    "kind": "theorem",
                    "status": "open",
                    "depth": 0,                 # ¬G is a new tree root
                    "question": statement,
                    "twin_of": goal_id,         # ¬G → G link at INSERT
                },
            },
            {
                "table": "goals",
                "op": "update",
                "id": goal_id,                  # snapshot G; new twin_of at finalize
            },
        ]
        ids = writer.begin_batch(ops)
        neg_id = ids[0]
        # ids[1] == goal_id

        # Step 2: stage_file
        Path(neg_lean_path).parent.mkdir(parents=True, exist_ok=True)
        writer.stage_file(neg_file["staging_path"], neg_lean_path)

        # Step 3: finalize. ¬G stays at status='open' (Builder/Backward
        # attack it). G gets twin_of=neg_id (G → ¬G link).
        writer.finalize("goals", neg_id, {})
        writer.finalize("goals", goal_id, {"twin_of": neg_id})
        return neg_id

    def _commit_dup(self, goal: dict, existing_neg_id: int) -> int:
        """¬G already exists (dedupe hit). Just update bidirectional twin_of.

        Two UPDATEs (¬G + G) wrapped in a begin_batch / finalize pair.
        No staging file write — ¬G's .lean is already on disk from prior
        commit. We do not modify that .lean file content.
        """
        writer = CommitWriter(self.conn)
        ops: list[dict[str, Any]] = [
            {"table": "goals", "op": "update", "id": existing_neg_id},
            {"table": "goals", "op": "update", "id": goal["id"]},
        ]
        writer.begin_batch(ops)

        writer.finalize("goals", existing_neg_id, {"twin_of": goal["id"]})
        writer.finalize("goals", goal["id"], {"twin_of": existing_neg_id})
        return existing_neg_id

    # ------------------------------------------------------------------
    # Pipeline lifecycle (parity with backward.py / builder.py)
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
                    pipeline_id, "Refuter", "atomic",
                    str(goal_id), "Goal", "running",
                    session_id, _now(),
                ),
            )

    def _finish_pipeline(self, pipeline_id: str, outcome: str) -> None:
        # outcome ∈ {success, exhausted}
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

    def run(self, goal_id: int) -> RefuterResult:
        """Run the full Refuter stage sequence for the given Goal G.

        Test hooks (mutually exclusive — see docs/dev/test_hooks.md):
          REFUTER_MOCK=success_negation → bypass agent; insert a stub ¬G
              with statement `False -- placeholder negation of <slug>`.
              For early P4 wiring tests where lake/agent are not in play.
          REFUTER_FORCE=exhausted        → return exhausted immediately.
          REFUTER_FORCE=succeed          → return success with no goal_id
              (test fixtures own the rows; P4 acceptance #1 enqueue test
              needs to assert pipeline outcome without writing rows).
          REFUTER_FAST_PATH=1            → reserved for P4 acceptance #6
              (Refuter→Builder fast path race). C29 acknowledges the env
              name; behavior added when cascade lands (C30).
        """
        mock = os.environ.get("REFUTER_MOCK")
        if mock == "success_negation":
            return self._mock_success_negation(goal_id)
        if mock is not None:
            raise ValueError(
                f"unknown REFUTER_MOCK value: {mock!r}; "
                "valid: 'success_negation'. For outcome forcing, use REFUTER_FORCE."
            )

        force = os.environ.get("REFUTER_FORCE")
        if force == "exhausted":
            return RefuterResult(outcome="exhausted")
        if force == "succeed":
            return RefuterResult(outcome="success")
        if force is not None:
            raise ValueError(
                f"unknown REFUTER_FORCE value: {force!r}; "
                "valid: 'exhausted' | 'succeed'."
            )

        try:
            goal = _row_as_dict(self.conn, "goals", goal_id)
        except ValueError:
            return RefuterResult(outcome="exhausted")

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

        result = self._run_loop(goal, pipeline_id, session_id, staging_dir, dead_attempts)
        self._finish_pipeline(pipeline_id, result.outcome)
        return result

    def _mock_success_negation(self, goal_id: int) -> RefuterResult:
        """Test-only: write a placeholder ¬G shell.

        Inserts a goals row with origin='refuter_negation' + bidirectional
        twin_of UPDATE; .lean file content is a stub. Used by acceptance #1
        (three-line dispatch: Backward + Refuter + Counterexample enqueue
        within 30s).
        """
        try:
            goal = _row_as_dict(self.conn, "goals", goal_id)
        except ValueError:
            return RefuterResult(outcome="exhausted")

        pipeline_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        self._insert_pipeline(pipeline_id, goal_id, session_id)

        slug = f"neg_{goal['slug']}"
        statement = f"False -- placeholder negation of {goal['slug']}"
        neg_lean_path = str(
            Path(self.config.base_dir)
            / "Problems" / goal["problem"]
            / "Goals" / f"{slug}.lean"
        )
        Path(neg_lean_path).parent.mkdir(parents=True, exist_ok=True)
        Path(neg_lean_path).write_text(
            f"-- Refuter mock negation of {goal['slug']}\n"
            f"theorem {slug} : {statement} := by sorry\n",
            encoding="utf-8",
        )

        writer = CommitWriter(self.conn)
        ops: list[dict[str, Any]] = [
            {
                "table": "goals",
                "op": "insert",
                "data": {
                    "problem": goal["problem"],
                    "slug": slug,
                    "lean_path": neg_lean_path,
                    "origin": "refuter_negation",
                    "kind": "theorem",
                    "status": "open",
                    "depth": 0,
                    "question": statement,
                    "twin_of": goal["id"],
                },
            },
            {"table": "goals", "op": "update", "id": goal["id"]},
        ]
        ids = writer.begin_batch(ops)
        neg_id = ids[0]
        writer.finalize("goals", neg_id, {})
        writer.finalize("goals", goal["id"], {"twin_of": neg_id})

        self._finish_pipeline(pipeline_id, "success")
        return RefuterResult(outcome="success", negation_goal_id=neg_id)

    def _run_loop(
        self,
        goal: dict,
        pipeline_id: str,
        session_id: str,
        staging_dir: str,
        dead_attempts: list[dict],
    ) -> RefuterResult:
        for _attempt in range(self.config.max_retries):
            shutil.rmtree(staging_dir, ignore_errors=True)
            Path(staging_dir).mkdir(parents=True, exist_ok=True)

            response = self._run_agent(goal, dead_attempts, session_id, staging_dir)
            if response is None:
                return RefuterResult(outcome="exhausted")

            negation = self._parse_negation(response.output)
            if negation is None:
                continue

            neg_file = self._write_staging(negation, staging_dir, goal)

            if not self._self_verify(neg_file):
                continue

            existing_neg_id = self._dedupe_against_existing(neg_file, goal)
            if existing_neg_id is not None:
                neg_id = self._commit_dup(goal, existing_neg_id)
                return RefuterResult(
                    outcome="success",
                    negation_goal_id=neg_id,
                    deduped=True,
                )

            neg_id = self._commit_novel(goal, neg_file, pipeline_id)
            return RefuterResult(
                outcome="success",
                negation_goal_id=neg_id,
                deduped=False,
            )

        return RefuterResult(outcome="exhausted")
