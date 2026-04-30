"""Builder + Backward pipelines. Pure functions over staging dir + DB.

Integrator atomicity = Hadamard backup-restore (no commit_state).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import agent, db, dedupe, manifest


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


_SORRY_STUB_RE = re.compile(r":=[ \t]*by[ \t]+sorry[ \t]*$", re.MULTILINE)


def _is_sorry_stub(content: str) -> bool:
    """True iff the file's proof body is a fresh `:= by sorry` placeholder.

    Phase 1 tactic_try rewrites the proof body via textual substitution and
    is only safe on this canonical form. After Backward replaces the body
    with a structured `have ... ; final_tac` patch, this returns False and
    Phase 1 must skip.
    """
    return _SORRY_STUB_RE.search(content) is not None


def _replace_proof_body(content: str, tactic: str) -> str:
    """Replace `:= by sorry` with `:= by <tactic>`. Caller must check
    `_is_sorry_stub` first; behavior on non-stub input is undefined."""
    cleaned = tactic.lstrip()
    if cleaned.startswith("by "):
        cleaned = cleaned[3:].lstrip()
    return _SORRY_STUB_RE.sub(f":= by {cleaned}", content, count=1)


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

    # Phase 1: tactic_try — only on fresh `:= by sorry` stubs.
    # Skips structured patches (post-Backward) and re-attempt scenarios
    # to avoid clobbering existing proof structure.
    if goal["attempts"] == 0 and _is_sorry_stub(source):
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
    """Verify a Strategy:
      1. lake build the strategy's scratch (re-elaborate against now-real
         sub-goal proofs);
      2. atomically rewrite the parent goal's lean_path to import the
         scratch and alias the proved theorem;
      3. lake build the parent. On any failure, restore the parent's
         pre-verify content.

    Returns outcome='proved' on full success, 'failed' otherwise. If the
    strategy has been superseded or the parent goal already proved, the
    pipeline returns outcome='failed' with reason='superseded' (cascade
    treats this as a no-op).
    """
    s = conn.execute(
        "SELECT s.*, g.status AS goal_status, g.slug AS goal_slug,"
        "       g.statement AS goal_statement, g.problem AS goal_problem"
        " FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE s.id = ?",
        (strategy_id,),
    ).fetchone()
    if s is None:
        return PipelineResult(outcome="failed",
                              failure_reason="strategy_not_found")

    if s["status"] == "superseded" or s["goal_status"] == "proved":
        return PipelineResult(outcome="failed", failure_reason="superseded")

    if not s["scratch_path"]:
        return PipelineResult(outcome="failed",
                              failure_reason="scratch_path_missing")

    scratch_abs = workspace / s["scratch_path"]
    if not scratch_abs.exists():
        return PipelineResult(outcome="failed",
                              failure_reason="scratch_file_missing",
                              failure_detail=str(scratch_abs))

    # Step 1: re-build scratch against now-real sub-goal proofs.
    ok, err = _lake_build(workspace, scratch_abs)
    if not ok:
        return PipelineResult(outcome="failed",
                              failure_reason="lake_build_error",
                              failure_detail=f"scratch: {err[:1900]}")

    # Step 2: rewrite parent's lean_path to alias from scratch.
    parent_abs = workspace / s["lean_path"]
    sid_token = f"s{strategy_id}"
    scratch_module = _lean_path_to_module(workspace, scratch_abs)

    original = parent_abs.read_text(encoding="utf-8") if parent_abs.exists() else ""
    orig_imports = [ln for ln in original.splitlines()
                    if ln.strip().startswith("import")]
    if f"import {scratch_module}" not in orig_imports:
        orig_imports.append(f"import {scratch_module}")
    new_content = (
        "\n".join(orig_imports) + "\n\n"
        f"namespace Problems.{s['goal_problem']}\n\n"
        f"theorem {s['goal_slug']} : {s['goal_statement']} := "
        f"{sid_token}_{s['goal_slug']}\n\n"
        f"end Problems.{s['goal_problem']}\n"
    )

    backup = parent_abs.with_suffix(parent_abs.suffix + ".verify_backup")
    if parent_abs.exists():
        shutil.copy2(parent_abs, backup)
    tmp = parent_abs.with_suffix(parent_abs.suffix + ".tmp")
    tmp.write_text(new_content, encoding="utf-8")
    os.replace(tmp, parent_abs)

    ok, err = _lake_build(workspace, parent_abs)
    if not ok:
        if backup.exists():
            shutil.copy2(backup, parent_abs)
            backup.unlink()
        return PipelineResult(outcome="failed",
                              failure_reason="lake_build_error",
                              failure_detail=f"parent: {err[:1900]}")

    if backup.exists():
        backup.unlink()
    return PipelineResult(outcome="proved")


# ---------------------------------------------------------------------
# Backward
# ---------------------------------------------------------------------

def run_backward(conn: sqlite3.Connection, *, goal_id: int,
                 workspace: Path, mfst: manifest.Manifest,
                 pipeline_id: str) -> PipelineResult:
    """OR-parallel-safe Backward.

    Each invocation reserves a fresh strategy id and writes its scratch +
    namespaced sub-goal files at strategy-isolated paths. Multiple
    concurrent Backwards on the same parent therefore never collide on
    the filesystem, the goals table (slug uniqueness), or the parent's
    own lean_path (which is left untouched until Verify wins).
    """
    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)

    # Reserve a strategy id up front so the agent can use it in slug names.
    # If we fail anywhere below we mark this row 'dead' (no orphan files).
    strategy_id = db.insert_strategy(
        conn, goal_id=goal_id, lean_path=goal["lean_path"],
        created_by=pipeline_id, proposal_md="", scratch_path="",
    )
    sid_token = f"s{strategy_id}"

    def _abort(reason: str, detail: str = "",
               proposal_md: str = "") -> PipelineResult:
        db.update_strategy_status(conn, strategy_id, "dead")
        return PipelineResult(
            outcome="failed", failure_reason=reason,
            failure_detail=detail, proposal_md=proposal_md,
        )

    agent.compile_context(conn, goal=goal, mfst=mfst,
                          attempts_dir=attempts_dir,
                          strategy_id=strategy_id)

    rc = agent.spawn_claude(
        kind="backward",
        prompt_path=PROMPT_DIR / "backward.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
    )
    if rc != 0:
        return _abort("agent_no_response", f"claude rc={rc}")

    proposal = attempts_dir / "PROPOSAL.md"
    if not proposal.exists():
        return _abort("parse_proposal_fail", "no PROPOSAL.md")
    proposal_text = proposal.read_text(encoding="utf-8")

    patches = list(attempts_dir.glob("patch*.lean"))
    new_subs = list(attempts_dir.glob("new_*.lean"))
    if not patches or not new_subs:
        return _abort(
            "parse_proposal_fail",
            f"patch={len(patches)} new={len(new_subs)}",
            proposal_text,
        )

    all_text = "\n".join(p.read_text(encoding="utf-8")
                         for p in patches + new_subs)
    forbidden = _grep_forbidden(all_text, mfst.forbidden_lemmas)
    if forbidden:
        return _abort("forbidden_lemma", forbidden, proposal_text)

    # Validate slug naming convention: every sub-goal filename must be
    # `new_<sid_token>_<parent_slug>_sub_<N>.lean`.
    expected_prefix = f"{sid_token}_{goal['slug']}_"
    sub_meta: list[tuple[str, Path]] = []  # (slug, source_in_attempts)
    for ns in new_subs:
        slug = _slug_from_filename(ns.name)
        if not slug.startswith(expected_prefix):
            return _abort(
                "naming_violation",
                f"sub-goal slug {slug!r} does not start with {expected_prefix!r}",
                proposal_text,
            )
        sub_meta.append((slug, ns))

    # Dedupe scan: for each candidate sub-goal, check whether an
    # ancestor goal in this problem has a matching conclusion (and
    # equal-or-fewer binders). Hits → write an alias lean file that
    # delegates to canonical via `apply <;> assumption`; insert the
    # alias goal as 'proved' (its proof IS the alias body).
    canonical_for: list[int | None] = []
    for slug, src in sub_meta:
        try:
            full_text = src.read_text(encoding="utf-8")
            concl = _extract_statement(full_text)
        except OSError:
            full_text = ""
            concl = ""
        canonical_for.append(
            dedupe.find_canonical(
                conn, workspace,
                problem=goal["problem"],
                parent_goal_id=goal_id,
                candidate_full_text=full_text,
                candidate_conclusion=concl,
            ) if concl else None
        )

    # Compute permanent paths under proofs/. No collision possible
    # because every path includes sid_token.
    proofs_dir = workspace / "Problems" / goal["problem"] / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    scratch_filename = f"_strategy_{sid_token}.lean"
    scratch_dest = proofs_dir / scratch_filename
    sub_dests = [(slug, proofs_dir / f"L_{slug}.lean") for slug, _ in sub_meta]

    placed: list[Path] = []
    try:
        # Place sub-goal files: alias body for dedupe-hits, original
        # content for novel sub-goals.
        for (slug, src), (_, dest), canonical_id in zip(
            sub_meta, sub_dests, canonical_for,
        ):
            if canonical_id is not None:
                canonical = db.get_goal(conn, canonical_id)
                canonical_module = _lean_path_to_module(
                    workspace, workspace / canonical["lean_path"])
                original_content = src.read_text(encoding="utf-8")
                dest.write_text(
                    dedupe.build_alias_content(
                        original_content=original_content,
                        canonical_module=canonical_module,
                        canonical_slug=canonical["slug"],
                    ),
                    encoding="utf-8",
                )
                print(f"[dedupe] {slug} → goal {canonical_id} "
                      f"({canonical['slug']})", flush=True)
            else:
                shutil.copy2(src, dest)
            placed.append(dest)
        shutil.copy2(patches[0], scratch_dest)
        placed.append(scratch_dest)

        # Build sub-goals first, then scratch (which imports them).
        for t in placed:
            ok, err = _lake_build(workspace, t)
            if not ok:
                raise RuntimeError(f"lake build {t.name} failed: {err[:500]}")

        # All passed — INSERT goals + link via strategy_subgoals.
        # Dedupe-hits are inserted as already-'proved' (alias body is
        # the proof); novel sub-goals start 'open'.
        linked_ids: list[int] = []
        for (slug, dest), canonical_id in zip(sub_dests, canonical_for):
            stmt = _extract_statement_from_lean(dest)
            rel = dest.relative_to(workspace).as_posix()
            new_gid = db.insert_goal(
                conn, problem=goal["problem"], slug=slug,
                lean_path=rel, statement=stmt, origin="backward",
                difficulty=max(1, goal["difficulty"] - 1),
                depth=goal["depth"] + 1,
            )
            if canonical_id is not None:
                db.update_goal_status(conn, new_gid, "proved")
            linked_ids.append(new_gid)
        for pos, gid in enumerate(linked_ids):
            db.link_subgoal(conn, strategy_id=strategy_id,
                            subgoal_id=gid, position=pos)

        scratch_rel = scratch_dest.relative_to(workspace).as_posix()
        db.update_strategy_scratch_path(conn, strategy_id, scratch_rel)
        conn.execute("UPDATE strategies SET proposal_md = ? WHERE id = ?",
                     (proposal_text, strategy_id))
        conn.commit()

        return PipelineResult(outcome="success", proposal_md=proposal_text)

    except Exception as exc:
        # Cleanup: remove only this strategy's files (other strategies
        # untouched). Mark this strategy dead.
        for p in placed:
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        return _abort("lake_build_error", str(exc)[:2000], proposal_text)


def _slug_from_filename(name: str) -> str:
    # new_<slug>.lean → <slug>
    base = name.removesuffix(".lean")
    return base.removeprefix("new_") if base.startswith("new_") else base


_THM_HEAD_RE = re.compile(r"\btheorem\s+\S+")


def _extract_statement(text: str) -> str:
    """Extract the type expression of the first `theorem` declaration.

    Handles explicit args `(x : T)`, implicit args `{α : Type*}`,
    instance args `[Inhabited α]`, and arbitrary depth of paren/brace/bracket
    nesting in the type itself. Returns the substring between the theorem's
    top-level `:` and the top-level `:=`.
    """
    m = _THM_HEAD_RE.search(text)
    if not m:
        return ""
    pos = m.end()
    n = len(text)

    # Skip leading arg blocks: ( ... ), { ... }, [ ... ]
    while pos < n:
        while pos < n and text[pos].isspace():
            pos += 1
        if pos >= n:
            return ""
        ch = text[pos]
        if ch in "({[":
            close = {"(": ")", "{": "}", "[": "]"}[ch]
            depth = 1
            pos += 1
            while pos < n and depth > 0:
                if text[pos] == ch:
                    depth += 1
                elif text[pos] == close:
                    depth -= 1
                pos += 1
            continue
        if ch == ":":
            pos += 1
            break
        return ""

    # Capture type until top-level `:=`
    start = pos
    dp = db_ = dk = 0
    while pos < n - 1:
        c = text[pos]
        if c == "(": dp += 1
        elif c == ")": dp -= 1
        elif c == "{": db_ += 1
        elif c == "}": db_ -= 1
        elif c == "[": dk += 1
        elif c == "]": dk -= 1
        elif c == ":" and text[pos + 1] == "=" and dp == 0 and db_ == 0 and dk == 0:
            return text[start:pos].strip()
        pos += 1
    return ""


def _extract_statement_from_lean(path: Path) -> str:
    return _extract_statement(path.read_text(encoding="utf-8"))
