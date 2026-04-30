"""WorkArea + Context.md compilation + LLM dispatch.

LLM provider selection lives in `Tooling.llm` (see `llm/base.py`).
This module orchestrates: sandbox dir, Context.md generation from DB,
and forwarding to the configured provider.

Context.md is Asterism's A7 improvement over Hadamard: structured
failure_reason + full proposal_md from prior dead_attempts injected
into agent's sandbox.
"""
from __future__ import annotations

import shutil
import sqlite3
import uuid
from pathlib import Path

from . import db, llm, manifest


WORKER_TIMEOUT_SEC = 600  # 10 min, see architecture.md §13


class WorkArea:
    """Ephemeral working area for one pipeline run.

    Holds two paths under `.attempts/`:
      * `attempts` = `.attempts/<pid>/`         agent sandbox, Context.md, outputs
      * `backup`   = `.attempts/_backup_<pid>/` Backward's pre-write proofs/ snapshot

    Both are unconditionally rmtree'd on `__exit__` (best-effort). A worker
    that needs to consume `backup` (e.g. Backward restoring on lake fail)
    must `shutil.move` it before the context exits — `__exit__` only cleans
    whatever is still on disk.
    """
    def __init__(self, workspace: Path, pipeline_id: str):
        self.workspace = workspace
        self.pipeline_id = pipeline_id
        self.attempts = workspace / ".attempts" / pipeline_id
        self.backup = workspace / ".attempts" / f"_backup_{pipeline_id}"

    def __enter__(self) -> "WorkArea":
        self.attempts.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for p in (self.attempts, self.backup):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        return False


def _attempts_dir(workspace: Path, pipeline_id: str) -> Path:
    d = workspace / ".attempts" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def compile_context(conn: sqlite3.Connection, *, goal: sqlite3.Row,
                    mfst: manifest.Manifest, attempts_dir: Path,
                    strategy_id: int | None = None) -> Path:
    """Write Context.md into attempts_dir. Pulls from DB + Manifest.

    `strategy_id`: when set (Backward worker), write a 'Naming convention'
    section instructing the agent to prefix all slugs with `s<sid>_`.
    Required for OR-parallel correctness — multiple Backwards on the same
    parent goal must produce non-colliding sub-goal slugs and theorem
    names.
    """
    parts: list[str] = []

    parts.append(f"# Context for goal {goal['slug']}")
    parts.append("")
    parts.append("## Goal statement")
    parts.append(goal["statement"])
    parts.append("")

    if strategy_id is not None:
        sid_token = f"s{strategy_id}"
        parent = goal["slug"]
        parts.append("## Naming convention (REQUIRED)")
        parts.append(
            f"This Backward attempt has been allocated strategy id "
            f"`{sid_token}`. Multiple strategies may race for this goal in "
            f"parallel; collision-free naming is mandatory."
        )
        parts.append("")
        parts.append(f"- Sub-goal slugs: `{sid_token}_sub_1`, "
                     f"`{sid_token}_sub_2`, ... — exactly `{sid_token}_sub_<N>`.")
        parts.append(f"- Sub-goal filenames: `new_{sid_token}_sub_<N>.lean`.")
        parts.append(f"- Sub-goal theorem name = sub-goal slug.")
        parts.append(f"- Patch filename: `patch_{parent}.lean` (parent slug, "
                     f"no `{sid_token}` prefix).")
        parts.append(f"- Patch theorem name: `{sid_token}` (NOT `{parent}` — "
                     f"that name belongs to the parent's lean file and "
                     f"would collide).")
        parts.append(f"- Patch imports: `import Problems.<problem>.proofs."
                     f"L_{sid_token}_sub_<N>` for each sub-goal.")
        parts.append("")

    if goal["origin"] == "backward":
        # Look up the parent goal + the strategy that produced this sub-goal
        # via strategy_subgoals → strategies → goals.
        row = conn.execute(
            "SELECT g.slug AS parent_slug, g.statement AS parent_statement,"
            "       s.proposal_md AS proposal_md "
            "FROM strategy_subgoals ss "
            "JOIN strategies s ON s.id = ss.strategy_id "
            "JOIN goals g ON g.id = s.goal_id "
            "WHERE ss.subgoal_id = ? "
            "ORDER BY ss.strategy_id ASC LIMIT 1",
            (goal["id"],),
        ).fetchone()
        if row:
            parts.append("## Parent goal & strategy")
            parts.append(f"This goal `{goal['slug']}` is a sub-goal of "
                         f"`{row['parent_slug']}`:")
            parts.append("")
            parts.append(f"> {row['parent_statement']}")
            parts.append("")
            if row["proposal_md"]:
                parts.append("Strategy that produced this sub-goal "
                             "(parent's PROPOSAL.md excerpt):")
                parts.append("```")
                parts.append(row["proposal_md"][:2000])
                parts.append("```")
                parts.append("")

    if mfst.mathlib_hints:
        parts.append("## Mathlib hints (from Manifest.md)")
        for h in mfst.mathlib_hints:
            parts.append(f"- {h}")
        parts.append("")

    if mfst.forbidden_lemmas:
        parts.append("## FORBIDDEN_LEMMAS (from Manifest.md)")
        parts.append("**Do NOT use any of the following in your proof or in any "
                     "sub-goal docstring; the integrator will reject the proposal.**")
        for f in mfst.forbidden_lemmas:
            parts.append(f"- {f}")
        parts.append("")

    if mfst.strategic_notes:
        parts.append("## Strategic notes (from Manifest.md)")
        parts.append(mfst.strategic_notes)
        parts.append("")

    deads = db.recent_dead_attempts(
        conn, target_id=goal["id"], target_kind="Goal", k=5
    )
    if deads:
        parts.append("## Previous attempts on THIS goal")
        for i, d in enumerate(deads, 1):
            parts.append(f"### Attempt {i} ({d['pipeline_id'][:12]}): {d['failure_reason']}")
            if d["failure_detail"]:
                detail = d["failure_detail"][:1000]
                parts.append("```")
                parts.append(detail)
                parts.append("```")
            if d["proposal_md"]:
                parts.append("Strategy summary (from PROPOSAL.md):")
                parts.append("```")
                parts.append(d["proposal_md"][:2000])
                parts.append("```")
            parts.append("")

    # Strategies of THIS goal that died at Verify (combined patch failed
    # lake build). The Backward that produced them stored its PROPOSAL.md
    # in strategies.proposal_md; surface that so the agent can avoid the
    # same combination pattern.
    strat_deads = conn.execute(
        "SELECT da.failure_reason, da.failure_detail, da.pipeline_id,"
        "       s.proposal_md AS strategy_proposal "
        "FROM dead_attempts da "
        "JOIN strategies s ON s.id = da.target_id "
        "WHERE da.target_kind = 'Strategy' AND s.goal_id = ? "
        "ORDER BY da.id DESC LIMIT 5",
        (goal["id"],),
    ).fetchall()
    if strat_deads:
        parts.append("## Past decompositions that failed Verify")
        parts.append("Earlier Backward attempts decomposed this goal but the "
                     "combination patch did not elaborate against the "
                     "sub-goal proofs. Avoid the same shape.")
        parts.append("")
        for i, d in enumerate(strat_deads, 1):
            parts.append(f"### Strategy {i} (pid {d['pipeline_id'][:12]}): "
                         f"{d['failure_reason']}")
            if d["failure_detail"]:
                parts.append("```")
                parts.append(d["failure_detail"][:1000])
                parts.append("```")
            if d["strategy_proposal"]:
                parts.append("Decomposition (from strategies.proposal_md):")
                parts.append("```")
                parts.append(d["strategy_proposal"][:2000])
                parts.append("```")
            parts.append("")

    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def spawn_llm(*, kind: str, prompt_path: Path, problem_dir: Path,
              attempts_dir: Path) -> int:
    """Dispatch to the configured LLM provider for one agent invocation.

    Provider is resolved from `ASTERISM_LLM_PROVIDER` env (default:
    `claude`). Returns the provider's rc (0 success, 124 timeout,
    127 missing dep, other = error).
    """
    return llm.get_provider().spawn(llm.LLMRequest(
        kind=kind,
        prompt_path=prompt_path,
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
        timeout_sec=WORKER_TIMEOUT_SEC,
    ))


# Back-compat alias: existing code (and any external callers) referencing
# `agent.spawn_claude` still work. Will be removed in a future cleanup
# once all in-tree call sites are migrated.
spawn_claude = spawn_llm


def new_pipeline_id() -> str:
    return str(uuid.uuid4())


def attempts_dir_for(workspace: Path, pipeline_id: str) -> Path:
    return _attempts_dir(workspace, pipeline_id)
