"""Builder pipeline (P1 simplified).

stages: tactic_try → commit
Hardcoded tactics: [rfl, simp, decide, norm_num, ring]
T_wall enforcement: force outcome=exhausted if wall-clock >= t_wall
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sqlite3

from Tooling.commit import CommitWriter
from Tooling.lake import run_lean


TACTICS: list[str] = ["rfl", "simp", "decide", "norm_num", "ring"]
DEFAULT_T_WALL: float = 30 * 60.0  # 30 minutes


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_as_dict(conn: sqlite3.Connection, table: str, row_id: int) -> dict[str, Any]:
    cur = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"{table} row {row_id} not found")
    return dict(zip([d[0] for d in cur.description], row))


def _replace_proof_body(content: str, tactic: str) -> str:
    """Replace proof body (everything from the last ':=') with 'by TACTIC'."""
    idx = content.rfind(":=")
    if idx == -1:
        return content
    return content[:idx] + f":= by {tactic}"


@dataclass
class BuilderConfig:
    t_wall: float = DEFAULT_T_WALL
    lake_timeout: float = 600.0
    base_dir: str = "."


@dataclass
class BuilderResult:
    outcome: str  # "proved" | "exhausted"
    tactic: str | None = None
    timed_out: bool = False


class Builder:
    def __init__(
        self,
        strategy_id: int,
        conn: sqlite3.Connection,
        config: BuilderConfig | None = None,
    ) -> None:
        self.strategy_id = strategy_id
        self.conn = conn
        self.config = config or BuilderConfig()
        self._writer = CommitWriter(conn)
        self._start: float = 0.0

    def run(self) -> BuilderResult:
        self._start = time.monotonic()
        p_uuid = str(uuid.uuid4())

        strategy = _row_as_dict(self.conn, "strategies", self.strategy_id)
        goal = _row_as_dict(self.conn, "goals", strategy["goal_id"])

        pipeline_id = self._insert_pipeline(p_uuid)
        staging_dir = self._staging_dir(goal, p_uuid)
        staging_dir.mkdir(parents=True, exist_ok=True)

        source_content = Path(strategy["lean_path"]).read_text(encoding="utf-8")
        proved_tactic: str | None = None
        proved_staging: Path | None = None
        dead: list[dict[str, Any]] = []
        timed_out = False

        for tactic in TACTICS:
            if time.monotonic() - self._start >= self.config.t_wall:
                timed_out = True
                break

            staging_lean = staging_dir / f"attempt_{tactic}.lean"
            staging_lean.write_text(
                _replace_proof_body(source_content, tactic), encoding="utf-8"
            )

            lake_result = run_lean(
                str(staging_lean),
                self.config.base_dir,
                timeout=self.config.lake_timeout,
            )

            if lake_result.outcome == "proved":
                proved_tactic = tactic
                proved_staging = staging_lean
                break
            else:
                dead.append(
                    {
                        "tactic": tactic,
                        "timed_out": lake_result.timed_out,
                        "messages": lake_result.messages,
                    }
                )

        if proved_tactic and proved_staging:
            self._commit_success(strategy, proved_staging)
            outcome = "proved"
        else:
            self._record_dead_attempts(dead, pipeline_id)
            outcome = "exhausted"

        self._finish_pipeline(pipeline_id, outcome)
        self._emit_event(
            "pipeline_finished",
            {"pipeline_id": pipeline_id, "strategy_id": self.strategy_id, "outcome": outcome},
        )

        return BuilderResult(outcome=outcome, tactic=proved_tactic, timed_out=timed_out)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _staging_dir(self, goal: dict[str, Any], p_uuid: str) -> Path:
        base = Path(self.config.base_dir)
        g_folder = f"{goal['id']}_{goal['slug']}"
        return base / "Problems" / goal["problem"] / "Goals" / g_folder / "Staging" / p_uuid

    def _insert_pipeline(self, p_uuid: str) -> str:
        with self.conn:
            self.conn.execute(
                "INSERT INTO pipelines "
                "(id, kind, runtime, target_id, target_kind, status, started_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    p_uuid, "Builder", "atomic",
                    str(self.strategy_id), "Strategy",
                    "running", _now(),
                ),
            )
        return p_uuid

    def _finish_pipeline(self, pipeline_id: str, outcome: str) -> None:
        status = "succeeded" if outcome == "proved" else "failed"
        with self.conn:
            self.conn.execute(
                "UPDATE pipelines SET status = ?, outcome = ?, finished_at = ? WHERE id = ?",
                (status, outcome, _now(), pipeline_id),
            )

    def _commit_success(self, strategy: dict[str, Any], staging_lean: Path) -> None:
        self._writer.begin("strategies", "update", row_id=self.strategy_id)
        self._writer.stage_file(staging_lean, strategy["lean_path"])
        self._writer.finalize("strategies", self.strategy_id, {"status": "succeeded"})

    def _record_dead_attempts(
        self,
        dead: list[dict[str, Any]],
        pipeline_id: str,
    ) -> None:
        now = _now()
        with self.conn:
            for attempt in dead:
                msgs = attempt.get("messages", [])
                kind_hint = next((m.get("kind", "") for m in msgs if m.get("kind")), "")
                if attempt.get("timed_out"):
                    reason = f"tactic {attempt['tactic']}: timed_out"
                elif kind_hint:
                    reason = f"tactic {attempt['tactic']}: {kind_hint}"
                else:
                    reason = f"tactic {attempt['tactic']}: failed"
                self.conn.execute(
                    "INSERT INTO dead_attempts "
                    "(target_id, target_kind, pipeline_id, pipeline_kind, "
                    "outcome, reason_summary, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(self.strategy_id), "Strategy",
                        pipeline_id, "Builder",
                        "exhausted", reason, now,
                    ),
                )

    def _emit_event(self, kind: str, payload: dict[str, Any]) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO events (kind, payload, ts) VALUES (?, ?, ?)",
                (kind, json.dumps(payload), _now()),
            )
