"""claude CLI spawn + Context.md compilation.

Context.md is the unique Asterism-over-Hadamard improvement (A7 from
Hadamard's deferred.md): structured failure_reason + full proposal_md
from prior dead_attempts injected into agent's sandbox.
"""
from __future__ import annotations

import shutil
import subprocess
import sqlite3
import uuid
from pathlib import Path

from . import db, manifest


WORKER_TIMEOUT_SEC = 600  # 10 min, see architecture.md §13


def _attempts_dir(workspace: Path, pipeline_id: str) -> Path:
    d = workspace / ".attempts" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def compile_context(conn: sqlite3.Connection, *, goal: sqlite3.Row,
                    mfst: manifest.Manifest, attempts_dir: Path) -> Path:
    """Write Context.md into attempts_dir. Pulls from DB + Manifest."""
    parts: list[str] = []

    parts.append(f"# Context for goal {goal['slug']}")
    parts.append("")
    parts.append("## Goal statement")
    parts.append(goal["statement"])
    parts.append("")

    if goal["origin"] == "backward":
        parent = conn.execute(
            "SELECT g.* FROM goals g JOIN strategy_subgoals ss ON ss.subgoal_id = g.id "
            "WHERE 0=1"  # we don't track parent_id directly; placeholder for future
        ).fetchone()
        if parent:
            parts.append("## Parent goal")
            parts.append(f"{parent['slug']}: {parent['statement']}")
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

    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


def spawn_claude(*, kind: str, prompt_path: Path, problem_dir: Path,
                 attempts_dir: Path, model: str = "claude-sonnet-4-6") -> int:
    """Run claude --agent <kind> with proper scope. Returns rc."""
    if not shutil.which("claude"):
        print("[agent] claude CLI not found; skipping spawn")
        return 127

    prompt = (
        f"{kind} task. Read agent prompt at {prompt_path} and follow it exactly.\n"
        f"Read context at {attempts_dir}/Context.md.\n"
        f"Write output to {attempts_dir}/."
    )

    cmd = [
        "claude",
        "--model", model,
        "-p", prompt,
        "--permission-mode", "acceptEdits",
        "--add-dir", str(problem_dir),
        "--add-dir", str(attempts_dir),
        "--no-session-persistence",
        "--output-format", "text",
    ]
    try:
        r = subprocess.run(
            cmd, timeout=WORKER_TIMEOUT_SEC,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        return r.returncode
    except subprocess.TimeoutExpired:
        print(f"[agent] claude timed out after {WORKER_TIMEOUT_SEC}s")
        return 124


def new_pipeline_id() -> str:
    return str(uuid.uuid4())


def attempts_dir_for(workspace: Path, pipeline_id: str) -> Path:
    return _attempts_dir(workspace, pipeline_id)
