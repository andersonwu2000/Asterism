"""Generalizer pipeline runtime (P7 C53).

Reads one proved Goal G and writes a candidate generalization G* — a more
general statement of which G is a special case. G* enters the graph as a
new tree root (origin='generalizer'); the framework then attacks G* with
Backward / Builder. There is NO automatic cascade: G* proved does NOT
mark the original G proved (architecture_pipelines.md §8: needs Cluster
typed relation, deferred to P8+).

Stages (architecture_pipelines.md §8):
  1. failure_replay  — read dead_attempts (target_kind='generalizer').
  2. agent           — read G statement + write candidate G* statement;
                       agent may early-exit `outcome: 'unproductive'`
                       claiming G is already maximally general.
  3. self_verify     — staging .lean elaborates (sorry stub OK).
                       [fail → retry agent]
  4. dedupe (any)    — G* vs Mathlib + Library + goals; dup → discard.
  5. commit          — INSERT goals (G*, origin='generalizer', depth=0)
                       + mv staging .lean. dup → no-op.

Outcome:
  success       — G* enters the graph as a new tree root.
  no_novel      — candidate matched an existing entry.
  unproductive  — agent self-reports G is already maximal.
  exhausted     — self_verify retry exhausted.
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

from Tooling.agent.provider import AgentResponse, FallbackChain, ModelResolver
from Tooling.commit import CommitWriter
from Tooling.lake import run_lean
from Tooling.subsystems.dedupe import dedupe as _stage_dedupe


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_as_dict(conn: sqlite3.Connection, table: str, row_id: int) -> dict:
    cur = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"{table} row {row_id} not found")
    return dict(zip([d[0] for d in cur.description], row))


@dataclass
class GeneralizerConfig:
    base_dir: str
    lake_cwd: str
    max_retries: int = 3
    lean_timeout: float = 600.0


@dataclass
class GeneralizerResult:
    outcome: str       # 'success' | 'no_novel' | 'unproductive' | 'exhausted'
    new_goal_id: int | None = None


class Generalizer:
    def __init__(
        self,
        conn: sqlite3.Connection,
        chain: FallbackChain,
        config: GeneralizerConfig,
        resolver: ModelResolver | None = None,
    ) -> None:
        self.conn = conn
        self.chain = chain
        self.config = config
        self.resolver = resolver or ModelResolver()

    # ------------------------------------------------------------------
    # Stage 1: failure_replay
    # ------------------------------------------------------------------

    def failure_replay(self, source_goal_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, reason_summary, ts FROM dead_attempts "
            "WHERE target_kind = 'forward' "
            "  AND target_id = ? "
            "  AND pipeline_kind = 'Generalizer' "
            "ORDER BY id DESC LIMIT 5",
            (str(source_goal_id),),
        ).fetchall()
        return [
            {"id": r[0], "reason_summary": r[1], "ts": r[2]} for r in rows
        ]

    # ------------------------------------------------------------------
    # Stage 2: agent
    # ------------------------------------------------------------------

    def _load_prompt(self) -> str:
        p = Path(__file__).parents[2] / "docs" / "prompts" / "generalizer.md"
        return p.read_text(encoding="utf-8")

    def _build_prompt(self, goal: dict, dead_attempts: list[dict]) -> str:
        template = self._load_prompt()
        return (
            template
            .replace("{{GOAL_PROBLEM}}", goal.get("problem") or "")
            .replace("{{GOAL_SLUG}}", goal.get("slug") or "")
            .replace("{{GOAL_STATEMENT}}", goal.get("question") or "")
            .replace("{{DEAD_ATTEMPTS}}", json.dumps(dead_attempts, indent=2))
        )

    def _run_agent(self, prompt: str, session_id: str,
                   staging_dir: str) -> AgentResponse | None:
        tier = self.resolver.resolve("generalizer", "agent")
        response, outcome = self.chain.run(
            model_tier=tier, prompt=prompt,
            scope_dirs=[staging_dir], session_id=session_id,
            staging_dir=staging_dir,
        )
        return response if outcome == "success" else None

    def _parse_response(self, output: str) -> dict | None:
        """Returns dict with shape:
          {'outcome': 'success', 'candidate': {'slug', 'statement'}}
          {'outcome': 'unproductive'}
        or None if malformed.
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
        outcome = obj.get("outcome")
        if outcome == "unproductive":
            return {"outcome": "unproductive"}
        if outcome != "success":
            return None
        cand = obj.get("candidate")
        if not isinstance(cand, dict):
            return None
        if not isinstance(cand.get("slug"), str) or not cand["slug"]:
            return None
        if not isinstance(cand.get("statement"), str) or not cand["statement"]:
            return None
        return {"outcome": "success", "candidate": cand}

    # ------------------------------------------------------------------
    # Stage 3: self_verify
    # ------------------------------------------------------------------

    def _write_staging(self, candidate: dict, staging_dir: str,
                       problem: str) -> dict:
        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        slug = candidate["slug"]
        stmt = candidate["statement"]
        staging_path = Path(staging_dir) / f"{slug}.lean"
        staging_path.write_text(
            f"import Problems.{problem}.Defs\n\n"
            f"theorem {slug} : {stmt} := by sorry\n",
            encoding="utf-8",
        )
        return {**candidate, "staging_path": str(staging_path)}

    def _self_verify(self, candidate: dict) -> bool:
        r = run_lean(
            candidate["staging_path"], self.config.lake_cwd,
            self.config.lean_timeout,
        )
        non_sorry = [m for m in r.messages if m.get("kind") != "hasSorry"]
        return (not r.timed_out) and (not non_sorry)

    # ------------------------------------------------------------------
    # Stage 4: dedupe
    # ------------------------------------------------------------------

    def _is_dup(self, candidate: dict, problem: str) -> bool:
        entry_rows = self.conn.execute(
            "SELECT id, lean_path FROM goals "
            "WHERE problem = ? AND commit_state = 'live'",
            (problem,),
        ).fetchall()
        entries = [{"id": int(r[0]), "lean_path": str(r[1])}
                   for r in entry_rows]
        cand_path = Path(candidate["staging_path"]).with_suffix(
            ".dedupe_cand.lean"
        )
        cand_path.write_text(
            f"theorem _candidate : {candidate['statement']} := sorry\n",
            encoding="utf-8",
        )
        try:
            result = _stage_dedupe(
                cand_path, entries, conn=self.conn, mode="strict",
            )
        finally:
            cand_path.unlink(missing_ok=True)
        return result.outcome == "hit"

    # ------------------------------------------------------------------
    # Stage 5: commit
    # ------------------------------------------------------------------

    def _commit(self, candidate: dict, problem: str) -> int:
        writer = CommitWriter(self.conn)
        op = {
            "table": "goals",
            "op": "insert",
            "data": {
                "problem": problem,
                "slug": candidate["slug"],
                "lean_path": "",
                "origin": "generalizer",
                "kind": "theorem",
                "status": "open",
                "depth": 0,
                "question": candidate["statement"],
            },
        }
        ids = writer.begin_batch([op])
        goal_id = ids[0]
        slug = candidate["slug"]
        canonical_rel = (
            f"Problems/{problem}/Goals/{goal_id}_{slug}/{slug}.lean"
        )
        canonical_abs = Path(self.config.base_dir) / canonical_rel
        canonical_abs.parent.mkdir(parents=True, exist_ok=True)
        writer.stage_file(candidate["staging_path"], str(canonical_abs))
        writer.finalize("goals", goal_id, {"lean_path": canonical_rel})
        return goal_id

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------

    def _insert_pipeline(self, pipeline_id: str, target_id: int,
                         session_id: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "session_id, started_at) VALUES "
                "(?, 'Generalizer', 'atomic', ?, 'Goal', 'running', ?, ?)",
                (pipeline_id, str(target_id), session_id, _now()),
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

    def run(self, source_goal_id: int) -> GeneralizerResult:
        """Run Generalizer on a proved seed Goal.

        Test hooks:
          GENERALIZER_FORCE=exhausted | no_novel | unproductive — force
          outcome (no agent call).
        """
        force = os.environ.get("GENERALIZER_FORCE")
        if force in {"exhausted", "no_novel", "unproductive"}:
            return GeneralizerResult(outcome=force)
        if force is not None:
            raise ValueError(
                f"unknown GENERALIZER_FORCE: {force!r}; "
                "valid: 'exhausted' | 'no_novel' | 'unproductive'."
            )

        try:
            seed = _row_as_dict(self.conn, "goals", source_goal_id)
        except ValueError:
            return GeneralizerResult(outcome="exhausted")
        if seed.get("status") != "proved":
            return GeneralizerResult(outcome="exhausted")

        problem = seed["problem"]
        pipeline_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        staging_dir = str(
            Path(self.config.base_dir)
            / "Problems" / problem / "_Generalizer" / session_id
        )
        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        self._insert_pipeline(pipeline_id, source_goal_id, session_id)

        dead_attempts = self.failure_replay(source_goal_id)
        prompt = self._build_prompt(seed, dead_attempts)

        candidate: dict | None = None
        for attempt in range(self.config.max_retries):
            retry_session_id = (
                str(uuid.uuid4()) if attempt > 0 else session_id
            )
            response = self._run_agent(prompt, retry_session_id, staging_dir)
            if response is None:
                continue
            parsed = self._parse_response(response.output)
            if parsed is None:
                continue
            if parsed["outcome"] == "unproductive":
                self._finish_pipeline(pipeline_id, "unproductive")
                return GeneralizerResult(outcome="unproductive")
            cand = self._write_staging(parsed["candidate"], staging_dir, problem)
            if not self._self_verify(cand):
                continue
            candidate = cand
            break

        if candidate is None:
            self._finish_pipeline(pipeline_id, "exhausted")
            return GeneralizerResult(outcome="exhausted")

        if self._is_dup(candidate, problem):
            self._finish_pipeline(pipeline_id, "no_novel")
            return GeneralizerResult(outcome="no_novel")

        new_id = self._commit(candidate, problem)
        self._finish_pipeline(pipeline_id, "success")
        return GeneralizerResult(outcome="success", new_goal_id=new_id)
