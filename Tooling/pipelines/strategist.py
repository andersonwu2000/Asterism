"""Strategist pipeline runtime (P7 C50).

Stages (architecture_pipelines.md §5):
  1. failure_replay  — read past Strategist decision rows + downstream
                       outcomes for the prompt's reflection section.
  2. inventory       — Tooling.strategist.inventory.collect(conn, problem).
  3. agent           — claude (or other configured provider) with the
                       Strategist prompt template.
  4. self_verify     — JSON schema validation on agent output.
                       [fail → retry from step 3, up to max_retries]
  5. commit          — INSERT one strategist_decisions row + invoke demux
                       (queue inserts + Goal status updates).

Cooldown: a single Strategist instance is in flight at any time globally.
Cooldown enforcement lives in the scheduler (the source that decides when
to enqueue a Strategist task); this module just runs one cycle when called.

Outcome enum:
    success   — decisions committed (possibly empty list)
    exhausted — agent failed to produce valid JSON within max_retries

Public API:
    Strategist(conn, chain, config, resolver=None)
    Strategist.run(problem) -> StrategistResult
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

from Tooling.agent.provider import AgentResponse, FallbackChain, ModelResolver
from Tooling.strategist.demux import DemuxResult, apply_decisions
from Tooling.strategist.inventory import collect


_INJECT_KINDS = {
    "Backward", "Refuter", "Forward", "Generalizer",
    "Counterexample", "ConstructionSearch",
}
_VALID_KINDS = _INJECT_KINDS | {"Shelve"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StrategistConfig:
    base_dir: str
    max_retries: int = 3
    max_decisions: int = 5            # M_strategist
    evidence_window: int = 20         # strategist.evidence_window
    decisions_lookback: int = 10      # strategist.decisions_lookback
    allowed_providers: list[str] | None = None


@dataclass
class StrategistResult:
    outcome: str                       # 'success' | 'exhausted'
    decisions_id: int | None = None
    raw_decisions: list[dict] = field(default_factory=list)
    demux: DemuxResult | None = None


class Strategist:
    def __init__(
        self,
        conn: sqlite3.Connection,
        chain: FallbackChain,
        config: StrategistConfig,
        resolver: ModelResolver | None = None,
    ) -> None:
        self.conn = conn
        self.chain = chain
        self.config = config
        self.resolver = resolver or ModelResolver()

    # ------------------------------------------------------------------
    # Stage 1: failure_replay (Strategist-specific)
    # ------------------------------------------------------------------
    #
    # Reads the last `decisions_lookback` strategist_decisions rows + joins
    # against any pipeline outcomes whose target_id appears in the row's
    # decisions list. The agent uses this to course-correct.

    def failure_replay(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, decisions, ts FROM strategist_decisions "
            "ORDER BY id DESC LIMIT ?",
            (self.config.decisions_lookback,),
        ).fetchall()
        out: list[dict] = []
        for row in rows:
            sd_id, decisions_raw, ts = row
            try:
                decisions = json.loads(decisions_raw) if decisions_raw else []
            except json.JSONDecodeError:
                decisions = []
            if not isinstance(decisions, list):
                decisions = []

            # For each decision, look up the most-recent pipeline that
            # was spawned against that target after this row's ts.
            joined: list[dict] = []
            for d in decisions:
                if not isinstance(d, dict):
                    continue
                target = d.get("target")
                kind = d.get("kind")
                if target is None or kind is None:
                    joined.append({"decision": d, "outcome": None})
                    continue
                p = self.conn.execute(
                    "SELECT outcome FROM pipelines "
                    "WHERE target_id = ? AND kind = ? AND started_at >= ? "
                    "ORDER BY started_at ASC LIMIT 1",
                    (str(target), kind, ts),
                ).fetchone()
                joined.append({
                    "decision": d,
                    "outcome": p[0] if p else None,
                })
            out.append({
                "decisions_id": sd_id,
                "ts": ts,
                "joined": joined,
            })
        return out

    # ------------------------------------------------------------------
    # Stage 2: inventory
    # ------------------------------------------------------------------

    def inventory(self, problem: str) -> dict:
        return collect(self.conn, problem)

    # ------------------------------------------------------------------
    # Stage 3: agent
    # ------------------------------------------------------------------

    def _load_prompt_template(self) -> str:
        prompt_path = Path(__file__).parents[2] / "docs" / "prompts" / "strategist.md"
        return prompt_path.read_text(encoding="utf-8")

    def _build_prompt(
        self,
        problem: str,
        inventory_data: dict,
        decisions_reflection: list[dict],
    ) -> str:
        template = self._load_prompt_template()
        meta = inventory_data.get("meta", {})
        return (
            template
            .replace("{{PROBLEM_NAME}}", problem)
            .replace("{{GENERATED_AT}}", str(meta.get("generated_at", "")))
            .replace("{{PER_GOAL}}", json.dumps(
                inventory_data.get("per_goal", []), indent=2))
            .replace("{{PER_SUBTREE}}", json.dumps(
                inventory_data.get("per_subtree", []), indent=2))
            .replace("{{TOP_N_GLOBAL}}", json.dumps(
                inventory_data.get("top_n_bad_goals_global", []), indent=2))
            .replace("{{EVIDENCE_WINDOW}}", str(self.config.evidence_window))
            .replace("{{EVIDENCE_RECENT}}", "[]")  # P7 C50 placeholder
            .replace("{{DECISIONS_LOOKBACK}}",
                     str(self.config.decisions_lookback))
            .replace("{{DECISIONS_REFLECTION}}", json.dumps(
                decisions_reflection, indent=2))
            .replace("{{M_STRATEGIST}}", str(self.config.max_decisions))
        )

    def _run_agent(
        self,
        prompt: str,
        session_id: str,
        staging_dir: str,
    ) -> AgentResponse | None:
        model_tier = self.resolver.resolve("strategist", "agent")
        response, outcome = self.chain.run(
            model_tier=model_tier,
            prompt=prompt,
            scope_dirs=[staging_dir],
            session_id=session_id,
            staging_dir=staging_dir,
        )
        return response if outcome == "success" else None

    # ------------------------------------------------------------------
    # Stage 4: self_verify (JSON schema)
    # ------------------------------------------------------------------

    def _parse_response(self, output: str) -> dict | None:
        """Extract the JSON block and verify shape. Return parsed dict or None."""
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', output)
        if not m:
            return None
        try:
            obj = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        decisions = obj.get("decisions")
        if not isinstance(decisions, list):
            return None
        if len(decisions) > self.config.max_decisions:
            return None
        for d in decisions:
            if not isinstance(d, dict):
                return None
            kind = d.get("kind")
            if kind not in _VALID_KINDS:
                return None
            target = d.get("target")
            if not isinstance(target, int):
                return None
            reason = d.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                return None
        return obj

    # ------------------------------------------------------------------
    # Stage 5: commit (INSERT row + demux)
    # ------------------------------------------------------------------

    def _commit(
        self,
        problem: str,
        decisions: list[dict],
    ) -> tuple[int, DemuxResult]:
        """Run demux first, then INSERT strategist_decisions row (R3 fix
        audit_c49_c50_c51.md HIGH-1: was previously two TXs with the row
        committed before demux, leaving an orphan row whenever demux's
        per-decision UPDATE/INSERT raised; failure_replay would later see
        a logged decision with no downstream pipeline outcome and
        misinterpret it as 'still running').

        New ordering: demux always runs (it never raises — failed decisions
        land in `rejected`). Then we INSERT the decisions row in a separate
        single-statement TX. Worst case is the row INSERT fails after demux
        side-effects landed; that means failure_replay misses one history
        entry — strictly less harmful than orphan row + bogus reflection.
        """
        demux = apply_decisions(
            self.conn,
            problem=problem,
            decisions=decisions,
            allowed_providers=self.config.allowed_providers,
        )
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO strategist_decisions (decisions, ts) "
                "VALUES (?, ?)",
                (json.dumps(decisions), _now()),
            )
            decisions_id = cur.lastrowid
        return decisions_id, demux

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------

    def _insert_pipeline(self, pipeline_id: str, problem: str,
                         session_id: str) -> None:
        # Strategist target is the Problem itself (no Goal id), encoded as
        # the string "_problem:<name>" so the pipelines.target_id NOT NULL
        # constraint is satisfied without forcing a Goal-id schema change.
        with self.conn:
            self.conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, "
                "session_id, started_at) VALUES "
                "(?, 'Strategist', 'atomic', ?, 'Goal', 'running', ?, ?)",
                (pipeline_id, f"_problem:{problem}", session_id, _now()),
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
    # Main orchestration
    # ------------------------------------------------------------------

    def run(self, problem: str) -> StrategistResult:
        """Run one Strategist cycle on `problem`.

        Test hooks (mutually exclusive — see docs/dev/test_hooks.md):
          STRATEGIST_FORCE=exhausted → return exhausted immediately
          STRATEGIST_FORCE=empty     → return success with empty decisions
        """
        force = os.environ.get("STRATEGIST_FORCE")
        if force == "exhausted":
            return StrategistResult(outcome="exhausted")
        if force == "empty":
            decisions_id, demux = self._commit(problem, [])
            self._consume_safely(problem)
            return StrategistResult(
                outcome="success",
                decisions_id=decisions_id,
                raw_decisions=[],
                demux=demux,
            )
        if force is not None:
            raise ValueError(
                f"unknown STRATEGIST_FORCE value: {force!r}; "
                "valid: 'exhausted' | 'empty'."
            )

        pipeline_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        staging_dir = str(
            Path(self.config.base_dir) / "Strategist" / session_id
        )
        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        self._insert_pipeline(pipeline_id, problem, session_id)

        decisions_reflection = self.failure_replay()
        inventory_data = self.inventory(problem)
        prompt = self._build_prompt(problem, inventory_data, decisions_reflection)

        parsed = None
        for _attempt in range(self.config.max_retries):
            retry_session_id = (
                str(uuid.uuid4()) if _attempt > 0 else session_id
            )
            response = self._run_agent(prompt, retry_session_id, staging_dir)
            if response is None:
                continue
            parsed = self._parse_response(response.output)
            if parsed is not None:
                break

        if parsed is None:
            self._finish_pipeline(pipeline_id, "exhausted")
            return StrategistResult(outcome="exhausted")

        decisions = parsed.get("decisions", [])
        decisions_id, demux = self._commit(problem, decisions)
        self._finish_pipeline(pipeline_id, "success")
        self._consume_safely(problem)
        return StrategistResult(
            outcome="success",
            decisions_id=decisions_id,
            raw_decisions=decisions,
            demux=demux,
        )

    def _consume_safely(self, problem: str) -> None:
        """Run round_robin.consume(problem) and emit an event on failure.

        R3 round 2 fix (audit2_c49_c50_c51.md H_R2-1 + H_R2-3): formerly
        each caller wrapped consume() in `except Exception: pass` — a
        silent-failure red-line violation (round-robin failures would
        invisibly stick the framework on one Problem). Plus duplicate code
        across the force=empty and main success paths. Centralise here.

        The architecture compliance for round-robin (phase7_smarts.md #10
        strict A→B→C→A rotation) depends on consume() succeeding. If it
        raises (DB BUSY/LOCKED, schema drift, conn closed), we emit an
        observable cascade event so an operator sees that round-robin is
        broken — instead of the framework silently re-selecting the same
        Problem next cycle.
        """
        from Tooling.strategist.round_robin import consume
        try:
            consume(self.conn, problem)
        except Exception as exc:
            try:
                with self.conn:
                    self.conn.execute(
                        "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                        ("cascade",
                         json.dumps({
                             "rule": "strategist_consume_failed",
                             "problem": problem,
                             "error": str(exc),
                         }),
                         _now()),
                    )
            except sqlite3.Error:
                # Even event-write failed — reraise the original so the
                # caller (Strategist.run) sees the failure rather than
                # double-silent.
                raise exc
