"""Forward pipeline runtime (P7 C52).

From a proved Goal as seed, derive a downstream corollary (e.g. G ⟹ H)
and INSERT it into the graph as an orphan Goal (origin='forward').

Stages (architecture_pipelines.md §4):
  1. failure_replay  — read dead_attempts (target_kind='forward').
  2. find_pattern    — list local proved Goals as seeds (regardless of
                       origin: root / backward / forward / refuter_negation).
  3. find_mathlib    — list relevant Mathlib entries to suppress dups.
  4. agent           — propose corollary candidates {slug, statement}.
  5. self_verify     — staging .lean elaborates (sorry stub OK).
                       [fail → retry agent]
  6. dedupe (any)    — candidate vs Mathlib + Library + goals.
                       dup → discard (no_novel, not failure).
  7. commit          — INSERT goals (origin='forward') + mv staging.

Outcome:
  success   — at least one novel Goal landed.
  no_novel  — all candidates were dups.
  exhausted — agent never produced valid candidates within max_retries.

Forward is Strategist-inject only (architecture §4 速查); no structural
refill triggers it. Caller signature is `run(seed_goal_id)`.
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
from Tooling.commit import CommitWriter
from Tooling.lake import run_lean
from Tooling.subsystems.dedupe import dedupe as _stage_dedupe
from Tooling.subsystems.search import search


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_as_dict(conn: sqlite3.Connection, table: str, row_id: int) -> dict:
    cur = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,))
    row = cur.fetchone()
    if row is None:
        raise ValueError(f"{table} row {row_id} not found")
    return dict(zip([d[0] for d in cur.description], row))


@dataclass
class ForwardConfig:
    base_dir: str
    lake_cwd: str
    max_retries: int = 3
    lean_timeout: float = 600.0


@dataclass
class ForwardResult:
    outcome: str            # 'success' | 'no_novel' | 'exhausted'
    new_goal_ids: list[int] = field(default_factory=list)


class Forward:
    def __init__(
        self,
        conn: sqlite3.Connection,
        chain: FallbackChain,
        config: ForwardConfig,
        resolver: ModelResolver | None = None,
    ) -> None:
        self.conn = conn
        self.chain = chain
        self.config = config
        self.resolver = resolver or ModelResolver()

    # ------------------------------------------------------------------
    # Stage 1: failure_replay (target_kind='forward')
    # ------------------------------------------------------------------

    def failure_replay(self, seed_goal_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, reason_summary, ts FROM dead_attempts "
            "WHERE target_kind = 'forward' AND target_id = ? "
            "ORDER BY id DESC LIMIT 5",
            (str(seed_goal_id),),
        ).fetchall()
        return [
            {"id": r[0], "reason_summary": r[1], "ts": r[2]} for r in rows
        ]

    # ------------------------------------------------------------------
    # Stage 2: find_pattern — local proved Goals (any origin)
    # ------------------------------------------------------------------

    def find_pattern(self, problem: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, slug, question FROM goals "
            "WHERE problem = ? AND status = 'proved' AND commit_state = 'live' "
            "ORDER BY id ASC",
            (problem,),
        ).fetchall()
        return [
            {"id": r[0], "slug": r[1], "statement": r[2] or ""}
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Stage 3: find_mathlib — Mathlib search (P3 stub still returns [])
    # ------------------------------------------------------------------

    def find_mathlib(self, seed: dict) -> list[dict]:
        # Best-effort; not failure-coupled.
        # R3 fix (audit HIGH-3): seed dict keys come from goals row schema
        # (`question`), not the agent-facing key `statement`. Old code
        # passed "" as query so Mathlib search was always empty.
        # R3 fix (audit MED-1 batch3): silent except violated red line; emit
        # an events row so the failure is observable instead of swallowed.
        query = seed.get("question") or ""
        try:
            r = search(
                query,
                scope="mathlib", kind="find_mathlib",
                conn=self.conn, lake_cwd=self.config.lake_cwd,
            )
            return r.results
        except RuntimeError as exc:
            self._emit_diagnostic("find_mathlib_failed", str(exc))
            return []

    def _emit_diagnostic(self, rule: str, detail: str) -> None:
        """Best-effort observability hook (mirrors Backward._emit_stage_fail)."""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO events (kind, payload, ts) VALUES "
                    "(?, ?, ?)",
                    ("cascade",
                     json.dumps({"rule": rule, "stage": "forward",
                                 "detail": detail}),
                     _now()),
                )
        except sqlite3.Error:
            pass

    # ------------------------------------------------------------------
    # Stage 4: agent
    # ------------------------------------------------------------------

    def _load_prompt(self) -> str:
        p = Path(__file__).parents[2] / "docs" / "prompts" / "forward.md"
        return p.read_text(encoding="utf-8")

    def _build_prompt(
        self,
        seed: dict,
        dead_attempts: list[dict],
        siblings: list[dict],
        mathlib_hits: list[dict],
    ) -> str:
        template = self._load_prompt()
        return (
            template
            .replace("{{SEED_PROBLEM}}", seed.get("problem") or "")
            .replace("{{SEED_SLUG}}",    seed.get("slug") or "")
            .replace("{{SEED_STATEMENT}}", seed.get("question") or "")
            .replace("{{DEAD_ATTEMPTS}}", json.dumps(dead_attempts, indent=2))
            .replace("{{SIBLINGS}}", json.dumps(
                [{"slug": s["slug"], "type": s["statement"]} for s in siblings],
                indent=2,
            ))
            .replace("{{MATHLIB_HITS}}", json.dumps(mathlib_hits, indent=2))
        )

    def _run_agent(self, prompt: str, session_id: str,
                   staging_dir: str) -> AgentResponse | None:
        tier = self.resolver.resolve("forward", "agent")
        response, outcome = self.chain.run(
            model_tier=tier, prompt=prompt,
            scope_dirs=[staging_dir], session_id=session_id,
            staging_dir=staging_dir,
        )
        return response if outcome == "success" else None

    def _parse_candidates(self, output: str) -> list[dict] | None:
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', output)
        if not m:
            return None
        try:
            obj = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        if obj.get("outcome") == "exhausted":
            return []
        cands = obj.get("candidates")
        if not isinstance(cands, list):
            return None
        for c in cands:
            if not isinstance(c, dict):
                return None
            if not isinstance(c.get("slug"), str) or not c["slug"]:
                return None
            if not isinstance(c.get("statement"), str) or not c["statement"]:
                return None
        return cands

    # ------------------------------------------------------------------
    # Stage 5: self_verify
    # ------------------------------------------------------------------

    def _write_staging(
        self, candidates: list[dict], staging_dir: str, problem: str
    ) -> list[dict]:
        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        out: list[dict] = []
        for c in candidates:
            slug = c["slug"]
            stmt = c["statement"]
            staging_path = Path(staging_dir) / f"{slug}.lean"
            staging_path.write_text(
                f"import Problems.{problem}.Defs\n\n"
                f"theorem {slug} : {stmt} := by sorry\n",
                encoding="utf-8",
            )
            out.append({**c, "staging_path": str(staging_path)})
        return out

    def _self_verify(self, candidates: list[dict]) -> tuple[bool, list[dict]]:
        all_pass = True
        out: list[dict] = []
        for c in candidates:
            r = run_lean(
                c["staging_path"], self.config.lake_cwd,
                self.config.lean_timeout,
            )
            non_sorry = [
                m for m in r.messages if m.get("kind") != "hasSorry"
            ]
            ok = (not r.timed_out) and (not non_sorry)
            if not ok:
                all_pass = False
            out.append({**c, "self_verify_pass": ok})
        return all_pass, out

    # ------------------------------------------------------------------
    # Stage 6: dedupe (any)
    # ------------------------------------------------------------------

    def _dedupe(self, candidates: list[dict], problem: str) -> list[dict]:
        # Build entries from ALL live goals in the problem (and Library/...
        # which is the proved.lean re-exports — represented in DB as
        # status='proved' rows, included automatically).
        entry_rows = self.conn.execute(
            "SELECT id, lean_path FROM goals "
            "WHERE problem = ? AND commit_state = 'live'",
            (problem,),
        ).fetchall()
        entries = [{"id": int(r[0]), "lean_path": str(r[1])}
                   for r in entry_rows]

        unique: list[dict] = []
        for c in candidates:
            cand_path = Path(c["staging_path"]).with_suffix(".dedupe_cand.lean")
            cand_path.write_text(
                f"theorem _candidate : {c['statement']} := sorry\n",
                encoding="utf-8",
            )
            try:
                result = _stage_dedupe(
                    cand_path, entries, conn=self.conn, mode="strict",
                )
            finally:
                cand_path.unlink(missing_ok=True)
            if result.outcome == "hit":
                continue
            unique.append(c)
        return unique

    # ------------------------------------------------------------------
    # Stage 7: commit
    # ------------------------------------------------------------------

    def _commit(
        self, candidates: list[dict], problem: str, pipeline_id: str
    ) -> list[int]:
        writer = CommitWriter(self.conn)
        ops: list[dict[str, Any]] = []
        # R3 fix (audit HIGH-2): goals.lean_path is NOT NULL UNIQUE; an empty
        # placeholder string conflicts on the second candidate. Use a UUID-
        # qualified placeholder per row (same pattern as cli.py:cmd_goal_add)
        # so begin_batch can INSERT N rows atomically; finalize() rewrites
        # to the canonical id-keyed path.
        for c in candidates:
            placeholder = (
                f"Problems/{problem}/Goals/_pending_{pipeline_id}_"
                f"{c['slug']}/{c['slug']}.lean"
            )
            ops.append({
                "table": "goals",
                "op": "insert",
                "data": {
                    "problem": problem,
                    "slug": c["slug"],
                    "lean_path": placeholder,
                    "origin": "forward",
                    "kind": "theorem",
                    "status": "open",
                    "depth": 0,
                    "question": c["statement"],
                },
            })
        ids = writer.begin_batch(ops) if ops else []
        for goal_id, c in zip(ids, candidates):
            slug = c["slug"]
            canonical_rel = f"Problems/{problem}/Goals/{goal_id}_{slug}/{slug}.lean"
            canonical_abs = Path(self.config.base_dir) / canonical_rel
            canonical_abs.parent.mkdir(parents=True, exist_ok=True)
            writer.stage_file(c["staging_path"], str(canonical_abs))
            writer.finalize("goals", goal_id, {"lean_path": canonical_rel})
        return ids

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
                "(?, 'Forward', 'atomic', ?, 'forward', 'running', ?, ?)",
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

    def run(self, seed_goal_id: int) -> ForwardResult:
        """Run Forward starting from a proved seed Goal.

        Test hooks:
          FORWARD_FORCE=exhausted | no_novel — force the outcome (no agent call).
        """
        force = os.environ.get("FORWARD_FORCE")
        if force == "exhausted":
            return ForwardResult(outcome="exhausted")
        if force == "no_novel":
            return ForwardResult(outcome="no_novel")
        if force is not None:
            raise ValueError(
                f"unknown FORWARD_FORCE value: {force!r}; "
                "valid: 'exhausted' | 'no_novel'."
            )

        try:
            seed = _row_as_dict(self.conn, "goals", seed_goal_id)
        except ValueError:
            return ForwardResult(outcome="exhausted")
        if seed.get("status") != "proved":
            # Forward only operates on proved seeds.
            return ForwardResult(outcome="exhausted")

        problem = seed["problem"]
        pipeline_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        staging_dir = str(
            Path(self.config.base_dir)
            / "Problems" / problem / "_Forward" / session_id
        )
        Path(staging_dir).mkdir(parents=True, exist_ok=True)
        self._insert_pipeline(pipeline_id, seed_goal_id, session_id)

        dead_attempts = self.failure_replay(seed_goal_id)
        siblings = self.find_pattern(problem)
        mathlib_hits = self.find_mathlib(seed)
        prompt = self._build_prompt(seed, dead_attempts, siblings, mathlib_hits)

        candidates: list[dict] | None = None
        for attempt in range(self.config.max_retries):
            retry_session_id = (
                str(uuid.uuid4()) if attempt > 0 else session_id
            )
            response = self._run_agent(prompt, retry_session_id, staging_dir)
            if response is None:
                continue
            cands = self._parse_candidates(response.output)
            if cands is None:
                continue
            if cands == []:
                # Agent self-reports exhaustion (no candidates worth proposing).
                self._finish_pipeline(pipeline_id, "exhausted")
                return ForwardResult(outcome="exhausted")
            cands_with_files = self._write_staging(cands, staging_dir, problem)
            all_ok, cands_with_files = self._self_verify(cands_with_files)
            if not all_ok:
                continue
            candidates = cands_with_files
            break

        if candidates is None:
            self._finish_pipeline(pipeline_id, "exhausted")
            return ForwardResult(outcome="exhausted")

        novel = self._dedupe(candidates, problem)
        if not novel:
            self._finish_pipeline(pipeline_id, "no_novel")
            return ForwardResult(outcome="no_novel")

        new_ids = self._commit(novel, problem, pipeline_id)
        self._finish_pipeline(pipeline_id, "success")
        return ForwardResult(outcome="success", new_goal_ids=new_ids)
