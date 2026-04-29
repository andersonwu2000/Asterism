"""Builder + Backward pipelines. Pure functions over staging dir + DB.

Integrator atomicity = Hadamard backup-restore (no commit_state).
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import agent, db, manifest


PROMPT_DIR = Path(__file__).parent / "prompts"

TACTIC_TRY_LIST = [
    "rfl", "simp", "decide", "trivial", "omega",
    "linarith", "nlinarith", "norm_num", "simp_all", "aesop",
]


@dataclass
class PipelineResult:
    outcome: str  # 'proved' | 'success' | 'exhausted' | 'failed'
    failure_reason: str = ""
    failure_detail: str = ""
    proposal_md: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)


def _collect_artifacts(attempts_dir: Path) -> dict[str, str]:
    """Snapshot all .md / .lean files in attempts_dir for forensic preservation
    in dead_attempts.artifacts JSON column."""
    out: dict[str, str] = {}
    for f in attempts_dir.glob("*"):
        if f.is_file() and f.suffix in {".md", ".lean"}:
            try:
                out[f.name] = f.read_text(encoding="utf-8")
            except OSError:
                pass
    return out


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _lean_path_to_module(workspace: Path, lean_path: Path) -> str:
    """Convert workspace-relative .lean path to lean module name.
    Problems/wilson/Root.lean → Problems.wilson.Root
    Problems/wilson/proofs/L_x.lean → Problems.wilson.proofs.L_x
    """
    rel = lean_path.relative_to(workspace).with_suffix("")
    return ".".join(rel.parts)


def _lake_build(workspace: Path, target_lean: Path) -> tuple[bool, str]:
    """Run `lake build <module>` (resolves dependencies). Returns (pass, output).

    Single-file `lake env lean` doesn't pull dependencies; if patch imports
    sub-goal modules they need to be built first. lake build does that.
    """
    module = _lean_path_to_module(workspace, target_lean)
    try:
        r = subprocess.run(
            ["lake", "build", module],
            cwd=str(workspace),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=600,
        )
        out = (r.stdout + r.stderr).strip()
        ok = r.returncode == 0 and "error:" not in out.lower()
        return ok, out
    except subprocess.TimeoutExpired:
        return False, f"lake build {module} timed out (600s)"


def _grep_forbidden(text: str, forbidden: list[str]) -> str | None:
    """Return the first forbidden lemma found, or None."""
    for lemma in forbidden:
        if "*" in lemma:
            pat = re.escape(lemma).replace(r"\*", r"[\w.]*")
        else:
            pat = re.escape(lemma)
        rx = re.compile(r"(?<![\w.])" + pat + r"(?![\w])")
        if rx.search(text):
            return lemma
    return None


def _replace_proof_body(content: str, tactic: str) -> str:
    """Replace everything after the last ':=' with `:= by <tactic>`."""
    idx = content.rfind(":=")
    if idx == -1:
        return content
    cleaned = tactic.lstrip()
    if cleaned.startswith("by "):
        cleaned = cleaned[3:].lstrip()
    return content[:idx] + f":= by {cleaned}"


# ---------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------

def run_builder(conn: sqlite3.Connection, *, goal_id: int,
                workspace: Path, mfst: manifest.Manifest,
                pipeline_id: str) -> PipelineResult:
    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")

    goal_lean = workspace / goal["lean_path"]
    if not goal_lean.exists():
        return PipelineResult(
            outcome="failed", failure_reason="lean_file_missing",
            failure_detail=str(goal_lean),
        )
    source = goal_lean.read_text(encoding="utf-8")

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)

    # Phase 1: tactic_try (in-place backup-restore)
    if goal["attempts"] == 0:
        backup_text = source
        for tac in TACTIC_TRY_LIST:
            new_text = _replace_proof_body(source, tac)
            goal_lean.write_text(new_text, encoding="utf-8")
            ok, _ = _lake_build(workspace, goal_lean)
            if ok:
                forbidden = _grep_forbidden(new_text, mfst.forbidden_lemmas)
                if not forbidden:
                    # Snapshot of the working tactic for forensics
                    (attempts_dir / f"won_{tac}.lean").write_text(
                        new_text, encoding="utf-8"
                    )
                    return PipelineResult(outcome="proved")
            # Restore for next try
            goal_lean.write_text(backup_text, encoding="utf-8")
        return PipelineResult(outcome="exhausted",
                              failure_reason="tactic_try_exhausted")

    # Phase 2: tactic_llm
    agent.compile_context(conn, goal=goal, mfst=mfst, attempts_dir=attempts_dir)
    rc = agent.spawn_claude(
        kind="builder",
        prompt_path=PROMPT_DIR / "builder.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
    )
    if rc != 0:
        return PipelineResult(outcome="failed", failure_reason="agent_no_response",
                              failure_detail=f"claude rc={rc}")

    proposal = (attempts_dir / "PROPOSAL.md")
    proposal_text = proposal.read_text(encoding="utf-8") if proposal.exists() else ""

    patches = list(attempts_dir.glob("patch*.lean"))
    if not patches:
        return PipelineResult(outcome="failed", failure_reason="agent_no_response",
                              failure_detail="no patch*.lean", proposal_md=proposal_text)
    patch = patches[0]
    patch_text = patch.read_text(encoding="utf-8")

    forbidden = _grep_forbidden(patch_text, mfst.forbidden_lemmas)
    if forbidden:
        return PipelineResult(
            outcome="failed", failure_reason="forbidden_lemma",
            failure_detail=forbidden, proposal_md=proposal_text,
        )

    # Stage: copy patch over goal lean (backup first)
    backup = goal_lean.with_suffix(goal_lean.suffix + ".backup")
    shutil.copy2(goal_lean, backup)
    shutil.copy2(patch, goal_lean)
    ok, err = _lake_build(workspace, goal_lean)
    if ok:
        backup.unlink()
        return PipelineResult(outcome="proved")
    shutil.copy2(backup, goal_lean)
    backup.unlink()
    return PipelineResult(
        outcome="failed", failure_reason="lake_build_error",
        failure_detail=err[:2000], proposal_md=proposal_text,
    )


# ---------------------------------------------------------------------
# Verify (Strategy)
# ---------------------------------------------------------------------

def run_verify(conn: sqlite3.Connection, *, strategy_id: int,
               workspace: Path, mfst: manifest.Manifest,
               pipeline_id: str) -> PipelineResult:
    """Verify a Strategy by re-building its parent goal lean file.

    All sub-goals of the strategy are already proved (this is enforced by
    `strategies_ready_for_builder` in dispatcher). The parent lean file
    holds the patch that combines them. We just re-run lake build to
    confirm it elaborates against the now-real sub-goal proofs.

    No agent spawn, no Phase 1 tactic_try, no proof body rewrite.
    """
    s = conn.execute(
        "SELECT * FROM strategies WHERE id = ?", (strategy_id,)
    ).fetchone()
    if s is None:
        return PipelineResult(outcome="failed", failure_reason="strategy_not_found")

    goal_lean = workspace / s["lean_path"]
    if not goal_lean.exists():
        return PipelineResult(
            outcome="failed", failure_reason="lean_file_missing",
            failure_detail=str(goal_lean),
        )

    ok, err = _lake_build(workspace, goal_lean)
    if ok:
        return PipelineResult(outcome="proved")
    return PipelineResult(
        outcome="failed", failure_reason="lake_build_error",
        failure_detail=err[:2000],
    )


# ---------------------------------------------------------------------
# Backward
# ---------------------------------------------------------------------

def run_backward(conn: sqlite3.Connection, *, goal_id: int,
                 workspace: Path, mfst: manifest.Manifest,
                 pipeline_id: str) -> PipelineResult:
    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    agent.compile_context(conn, goal=goal, mfst=mfst, attempts_dir=attempts_dir)

    rc = agent.spawn_claude(
        kind="backward",
        prompt_path=PROMPT_DIR / "backward.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
    )
    if rc != 0:
        return PipelineResult(outcome="failed", failure_reason="agent_no_response",
                              failure_detail=f"claude rc={rc}")

    proposal = attempts_dir / "PROPOSAL.md"
    if not proposal.exists():
        return PipelineResult(outcome="failed", failure_reason="parse_proposal_fail",
                              failure_detail="no PROPOSAL.md")
    proposal_text = proposal.read_text(encoding="utf-8")

    patches = list(attempts_dir.glob("patch*.lean"))
    new_subs = list(attempts_dir.glob("new_*.lean"))
    if not patches or not new_subs:
        return PipelineResult(
            outcome="exhausted", failure_reason="parse_proposal_fail",
            failure_detail=f"patch={len(patches)} new={len(new_subs)}",
            proposal_md=proposal_text,
        )

    all_text = "\n".join(p.read_text(encoding="utf-8")
                         for p in patches + new_subs)
    forbidden = _grep_forbidden(all_text, mfst.forbidden_lemmas)
    if forbidden:
        return PipelineResult(
            outcome="failed", failure_reason="forbidden_lemma",
            failure_detail=forbidden, proposal_md=proposal_text,
        )

    # Integrator: backup + place files + lake build
    proofs_dir = workspace / "Problems" / goal["problem"] / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = workspace / ".attempts" / f"_backup_{pipeline_id}"
    if proofs_dir.exists():
        shutil.copytree(proofs_dir, backup_dir, dirs_exist_ok=True)

    sub_meta: list[tuple[str, Path]] = []  # (slug, dest_path)
    try:
        # Place sub-goal files first
        for ns in new_subs:
            slug = _slug_from_filename(ns.name)
            dest = proofs_dir / f"L_{slug}.lean"
            shutil.copy2(ns, dest)
            sub_meta.append((slug, dest))

        # Place parent patch (overwriting goal lean)
        goal_lean = workspace / goal["lean_path"]
        shutil.copy2(patches[0], goal_lean)

        # Build all touched
        targets = [goal_lean] + [m[1] for m in sub_meta]
        for t in targets:
            ok, err = _lake_build(workspace, t)
            if not ok:
                raise RuntimeError(f"lake build {t.name} failed: {err[:500]}")

        # All passed — INSERT DB rows
        max_id = conn.execute(
            "SELECT COALESCE(MAX(id), 0) AS m FROM goals"
        ).fetchone()["m"]
        new_goal_ids: list[int] = []
        for slug, dest in sub_meta:
            stmt = _extract_statement_from_lean(dest)
            rel = dest.relative_to(workspace).as_posix()
            new_goal_ids.append(db.insert_goal(
                conn, problem=goal["problem"], slug=slug,
                lean_path=rel, statement=stmt, origin="backward",
                difficulty=max(1, goal["difficulty"] - 1),
                depth=goal["depth"] + 1,
            ))

        strategy_id = db.insert_strategy(
            conn, goal_id=goal_id,
            lean_path=goal["lean_path"],
            created_by=pipeline_id,
            proposal_md=proposal_text,
        )
        for pos, sgid in enumerate(new_goal_ids):
            db.link_subgoal(conn, strategy_id=strategy_id,
                            subgoal_id=sgid, position=pos)

        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        return PipelineResult(outcome="success", proposal_md=proposal_text)

    except Exception as exc:
        # Restore backup
        if backup_dir.exists():
            shutil.rmtree(proofs_dir)
            shutil.move(str(backup_dir), str(proofs_dir))
        return PipelineResult(
            outcome="failed", failure_reason="lake_build_error",
            failure_detail=str(exc)[:2000], proposal_md=proposal_text,
        )


def _slug_from_filename(name: str) -> str:
    # new_<slug>.lean → <slug>
    base = name.removesuffix(".lean")
    return base.removeprefix("new_") if base.startswith("new_") else base


_THM_RE = re.compile(r"theorem\s+\S+\s*:\s*(.+?)\s*:=", re.DOTALL)


def _extract_statement_from_lean(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = _THM_RE.search(text)
    return m.group(1).strip() if m else ""
