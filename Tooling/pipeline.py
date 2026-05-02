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
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import agent, db, dedupe, diagnostics, manifest


PROMPT_DIR = Path(__file__).parent / "prompts"

# F46 — wall-clock threshold under which a non-zero spawn is reclassified
# as `spawn_fast_fail`. Real claude.exe launches take ~3-5s and the
# fastest legitimate failure (e.g. compilation rejection of malformed
# patch) needs at least one model turn, so 10s is a conservative bound.
# Below this floor, the rc≠0 is almost certainly an infra fault (cwd /
# permission / network / claude.exe crash) rather than agent error.
SPAWN_FAST_FAIL_SEC = 10.0


def _spawn_failure(rc: int, attempts_dir: Path,
                   spawn_dur: float) -> tuple[str, str]:
    """F46 — classify a non-zero `agent.spawn_llm` rc into
    (failure_reason, failure_detail). When wall-clock < 10s the agent
    almost certainly never ran (claude.exe crashed at startup, prompt
    parser rejected, cwd unreachable, ...) so the call is reclassified
    as `spawn_fast_fail`. Pipeline cascade treats this differently:
    no goal-attempt increment, dispatcher sets a per-target cooldown.

    Reads `attempts_dir/_spawn.stderr` (written by the provider on
    rc≠0) and folds the first ~600 chars into failure_detail so
    forensic visibility doesn't depend on grovelling through orphan
    sandbox dirs."""
    stderr_tail = ""
    sf = attempts_dir / "_spawn.stderr"
    if sf.exists():
        try:
            stderr_tail = sf.read_text(encoding="utf-8")[:600].strip()
        except OSError:
            stderr_tail = ""
    base = f"agent rc={rc}"
    if spawn_dur < SPAWN_FAST_FAIL_SEC:
        base = f"agent rc={rc} (fast-fail in {spawn_dur:.1f}s)"
        reason = "spawn_fast_fail"
    else:
        reason = "agent_no_response"
    detail = base if not stderr_tail else f"{base}\n{stderr_tail}"
    return reason, detail

# Fast-path tactic closers tried (each via single `lake env lean`)
# before any LLM call. Order: cheapest first, most general last. Each
# hit saves an entire Builder pipeline (~$0.05 face-value + ~270s
# wall + thinking budget); cumulative ~30s lake-env startup overhead
# when all fail is more than offset by any single hit. Confirmed
# real Lean 4 / Mathlib names (no `polyrith` — needs SAGE binary).
TACTIC_TRY_LIST = [
    # Trivial / instant
    "rfl", "decide", "trivial",
    # Numeric / linear
    "norm_num", "omega",
    # Cast normalization
    "norm_cast", "push_cast",
    # General simp
    "simp",
    # Algebraic identities
    "ring", "ring_nf", "field_simp",
    # Arithmetic search
    "linarith", "nlinarith",
    # Positivity
    "positivity",
    # Heavier simp
    "simp_all",
    # Decision procedures
    "grind",   # Lean 4.30+ general decision procedure
    "aesop",   # general proof search
]


_IMPORT_LINE_RE = re.compile(r"(?m)^import\s")


def _ensure_import_mathlib(content: str) -> str:
    """Prepend `import Mathlib` if the file has no `import` line at all.

    Weaker LLMs (e.g. Haiku) sometimes write a lemma file with no
    imports and reference Mathlib types like `ZMod` or `Nat.factorial`,
    causing every reference to fail as `Unknown constant ...`. Files
    that already declare any specific import are left untouched —
    duplicate umbrella import is harmless in Lean 4 but we don't want
    to second-guess intentional minimal imports.
    """
    if _IMPORT_LINE_RE.search(content):
        return content
    return "import Mathlib\n\n" + content


@dataclass
class PipelineResult:
    outcome: str  # 'proved' | 'success' | 'exhausted' | 'failed'
    failure_reason: str = ""
    failure_detail: str = ""
    proposal_md: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)


def _collect_artifacts(attempts_dir: Path) -> dict[str, str]:
    """Snapshot all .md / .lean / .txt files in attempts_dir for forensic
    preservation in dead_attempts.artifacts JSON column. .txt covers
    `_raw_response.txt` written by the OpenAI provider (raw model output
    before fence parsing) — needed when fence-parse failures point
    blame at the model's output schema."""
    out: dict[str, str] = {}
    for f in attempts_dir.glob("*"):
        if f.is_file() and f.suffix in {".md", ".lean", ".txt"}:
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


def _lake_build_modules(workspace: Path,
                        modules: list[str]) -> tuple[bool, str]:
    """Run `lake build <m1> <m2> ...` for one or many module names.

    Lake's internal scheduler resolves the dependency DAG and builds
    independent modules in parallel. Passing N modules in a single
    call is therefore much faster than N sequential single-target
    invocations whenever any of those modules can run in parallel
    (e.g. Backward writes 4 sibling sub-goal files plus 1 strategy
    file that imports them all — sub-goals build concurrently, then
    the strategy serially).
    """
    try:
        r = subprocess.run(
            ["lake", "build", *modules],
            cwd=str(workspace),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=600,
        )
        out = (r.stdout + r.stderr).strip()
        ok = r.returncode == 0 and "error:" not in out.lower()
        return ok, out
    except subprocess.TimeoutExpired:
        return False, f"lake build {' '.join(modules)} timed out (600s)"


def _lake_build(workspace: Path, target_lean: Path) -> tuple[bool, str]:
    """Build a single .lean file's module (resolves deps).

    Thin wrapper around `_lake_build_modules` — kept for Builder / Verify
    call sites that only ever build one target at a time.
    """
    module = _lean_path_to_module(workspace, target_lean)
    return _lake_build_modules(workspace, [module])


def _lake_build_batch(workspace: Path,
                      targets: list[Path]) -> tuple[bool, str]:
    """Build multiple .lean files in one lake invocation. Lake
    parallelizes independent targets internally."""
    modules = [_lean_path_to_module(workspace, t) for t in targets]
    return _lake_build_modules(workspace, modules)


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

def _fetch_last_builder_error(conn: sqlite3.Connection,
                              goal_id: int) -> str:
    """F33 — return the smart-truncated lake error from this goal's
    most recent Builder dead_attempt. Used as `retry_context` inlined
    into the retry prompt (no separate file needed — agent sees the
    error immediately, no Read tool round-trip)."""
    row = conn.execute(
        "SELECT da.failure_detail FROM dead_attempts da"
        " JOIN pipelines p ON p.id = da.pipeline_id"
        " WHERE da.target_id = ? AND da.target_kind = 'Goal'"
        "   AND p.kind = 'Builder'"
        " ORDER BY da.id DESC LIMIT 1",
        (goal_id,),
    ).fetchone()
    if row is None or not row["failure_detail"]:
        return ""
    return diagnostics.strip_lake_noise(row["failure_detail"])


def run_builder(conn: sqlite3.Connection, *, goal_id: int,
                workspace: Path, mfst: manifest.Manifest,
                pipeline_id: str) -> PipelineResult:
    import uuid

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

    # Phase 2: tactic_llm with F33 same-session retry.
    # First attempt mints a session id and pins it via --session-id;
    # subsequent attempts reuse via --resume + a short RETRY_NOTE.md
    # that relies on the prior turn living in claude's session memory.
    sid = db.get_builder_session_id(conn, goal_id)
    is_retry = sid is not None
    retry_context: str | None = None
    if not is_retry:
        sid = str(uuid.uuid4())
        db.set_builder_session_id(conn, goal_id, sid)
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir, kind="builder")
    else:
        retry_context = _fetch_last_builder_error(conn, goal_id)

    spawn_t0 = time.monotonic()
    rc = agent.spawn_llm(
        kind="builder",
        prompt_path=PROMPT_DIR / "builder.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
        session_id=sid,
        is_retry=is_retry,
        retry_context=retry_context,
    )
    spawn_dur = time.monotonic() - spawn_t0

    # F33 — fallback for stale session (claude's on-disk session was
    # GC'd or the daemon's DB id outlived the file). One-time retry
    # with a fresh uuid down the cold path.
    if rc == 125:
        db.set_builder_session_id(conn, goal_id, None)
        sid = str(uuid.uuid4())
        db.set_builder_session_id(conn, goal_id, sid)
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir, kind="builder")
        spawn_t0 = time.monotonic()
        rc = agent.spawn_llm(
            kind="builder",
            prompt_path=PROMPT_DIR / "builder.md",
            problem_dir=workspace / "Problems" / goal["problem"],
            attempts_dir=attempts_dir,
            session_id=sid,
            is_retry=False,
        )
        spawn_dur = time.monotonic() - spawn_t0

    if rc == 124:
        # Timeout: the agent's session may have been killed mid-write
        # (claude's session file, gemini's in-flight API call, etc).
        # Conservative: clear session_id so next attempt cold-starts.
        db.set_builder_session_id(conn, goal_id, None)
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return PipelineResult(outcome="failed",
                              failure_reason=reason,
                              failure_detail=detail)
    if rc != 0:
        # Ordinary failure: keep session_id so next attempt's --resume
        # has the prior failed-turn context to learn from. (Gemini /
        # OpenAI providers ignore session_id — clearing on rc=124 only.)
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return PipelineResult(outcome="failed",
                              failure_reason=reason,
                              failure_detail=detail)

    proposal = (attempts_dir / "PROPOSAL.md")
    proposal_text = proposal.read_text(encoding="utf-8") if proposal.exists() else ""

    patches = list(attempts_dir.glob("patch*.lean"))
    if not patches:
        # F48 — Builder decline channel. The agent followed builder.md's
        # "When to skip writing a patch" hatch: it produced a non-empty
        # PROPOSAL.md explaining why the goal is too hard / needs
        # decomposition, but did not write patch.lean. Cascade treats
        # this distinctly from agent_no_response: it jumps the goal to
        # Backward immediately rather than letting BUILDER_THRESHOLD
        # run out on attempts the agent already said are unwinnable.
        if proposal_text.strip():
            return PipelineResult(
                outcome="failed", failure_reason="agent_declined",
                failure_detail="builder declined; PROPOSAL.md explains why",
                proposal_md=proposal_text,
            )
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
        failure_detail=diagnostics.annotate_failure_detail(err),
        proposal_md=proposal_text,
    )


# ---------------------------------------------------------------------
# Verify (Strategy)
# ---------------------------------------------------------------------

def _verify_patch_retry(
    conn: sqlite3.Connection, *,
    workspace: Path, pipeline_id: str,
    strategy: sqlite3.Row,
    scratch_abs: Path,
    lake_err: str,
) -> tuple[bool, str | None]:
    """F41 — one-shot LLM repair when scratch lake_build failed.

    Common Verify failure pattern: every sub-goal proves individually
    (lake build OK in isolation), but the strategy combination patch
    fails to elaborate due to implicit-arg / typeclass drift between
    what the patch expected and what the sub-goals actually expose.
    Default cascade response is to mark strategy dead, increment the
    parent goal's attempts, and let Backward re-decompose — re-proving
    every sub-goal from scratch. Expensive.

    This helper intercepts: snapshot the original patch, ask the LLM
    once to rewrite ONLY the strategy's tactic block (sub-goals stay
    untouched), re-build. On success we return (True, None) and the
    caller proceeds to Step 2 (parent rewrite). On failure (rc!=0,
    no patch.lean, or lake still rejects) we restore the original
    patch and return (False, new_err) so the caller can drop into
    the standard failure path with no behavior change.

    Off via `ASTERISM_VERIFY_RETRY=0`. Default on.
    """
    if os.environ.get("ASTERISM_VERIFY_RETRY", "1") == "0":
        return False, None

    backup = scratch_abs.with_suffix(scratch_abs.suffix + ".verify_retry_backup")
    shutil.copy2(scratch_abs, backup)

    # Reuse the existing pipeline's attempts dir (created by WorkArea
    # in dispatcher) — the original Verify pipeline doesn't write
    # anything into it, so it's empty and safe to populate.
    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)

    # Pull each sub-goal's lean file content so the LLM sees the
    # actual proved signatures + bodies. Order by strategy_subgoals
    # position to match how the patch references them.
    sub_rows = conn.execute(
        "SELECT g.lean_path, g.slug FROM strategy_subgoals ss "
        "JOIN goals g ON g.id = ss.subgoal_id "
        "WHERE ss.strategy_id = ? ORDER BY ss.position",
        (int(strategy["id"]),),
    ).fetchall()

    parts: list[str] = [
        f"# Verify retry — strategy s{strategy['id']}",
        "",
        "The strategy patch failed to elaborate against the now-real "
        "sub-goal proofs. Rewrite the strategy patch so the elaboration "
        "goes through. Do NOT modify the sub-goal proofs.",
        "",
        "## Original strategy patch (failed Verify)",
        "",
        "```lean",
        scratch_abs.read_text(encoding="utf-8"),
        "```",
        "",
        "## Sub-goal proofs (correct, signatures fixed)",
        "",
    ]
    for r in sub_rows:
        path = workspace / r["lean_path"]
        if not path.exists():
            continue
        parts.append(f"### `{path.name}` (slug `{r['slug']}`)")
        parts.append("")
        parts.append("```lean")
        parts.append(path.read_text(encoding="utf-8"))
        parts.append("```")
        parts.append("")
    parts.append("## Verify lake stderr (the failure to fix)")
    parts.append("")
    parts.append("```")
    parts.append(diagnostics.smart_truncate_stderr(lake_err))
    parts.append("```")
    parts.append("")
    (attempts_dir / "Context.md").write_text(
        "\n".join(parts), encoding="utf-8")

    # Spawn LLM. Use kind='builder' so it picks up the Builder model
    # tier (cheap-LLM is fine for a tactic-block rewrite). Cold spawn
    # — no F33 session, no retry context.
    rc = agent.spawn_llm(
        kind="builder",
        prompt_path=PROMPT_DIR / "verify_retry.md",
        problem_dir=workspace / "Problems" / strategy["goal_problem"],
        attempts_dir=attempts_dir,
        session_id=None,
        is_retry=False,
        retry_context=None,
    )
    if rc != 0:
        shutil.copy2(backup, scratch_abs)
        backup.unlink()
        return False, None

    new_patch = attempts_dir / "patch.lean"
    if not new_patch.exists():
        shutil.copy2(backup, scratch_abs)
        backup.unlink()
        return False, None

    shutil.copy2(new_patch, scratch_abs)
    ok, new_err = _lake_build(workspace, scratch_abs)
    if ok:
        backup.unlink()
        return True, None
    shutil.copy2(backup, scratch_abs)
    backup.unlink()
    return False, new_err


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
        # F41 — try one LLM-driven repair before giving up. Common
        # failure mode is type-drift (sub-goals individually OK but
        # combined patch elaboration fails); cheap retry can fix
        # without losing the sub-goal proofs.
        retry_ok, retry_err = _verify_patch_retry(
            conn, workspace=workspace, pipeline_id=pipeline_id,
            strategy=s, scratch_abs=scratch_abs, lake_err=err,
        )
        if retry_ok:
            print(f"[verify_retry] strategy=s{strategy_id} succeeded",
                  flush=True)
            ok, err = True, ""  # fall through to Step 2
        else:
            if retry_err is not None:
                print(f"[verify_retry] strategy=s{strategy_id} attempted "
                      f"but lake still rejects", flush=True)
            return PipelineResult(
                outcome="failed", failure_reason="lake_build_error",
                failure_detail=diagnostics.annotate_failure_detail(
                    f"scratch: {err}"),
            )

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
        f"{sid_token}\n\n"
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
        return PipelineResult(
            outcome="failed", failure_reason="lake_build_error",
            failure_detail=diagnostics.annotate_failure_detail(
                f"parent: {err}"),
        )

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
                          strategy_id=strategy_id, kind="backward")

    spawn_t0 = time.monotonic()
    rc = agent.spawn_llm(
        kind="backward",
        prompt_path=PROMPT_DIR / "backward.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
    )
    if rc != 0:
        spawn_dur = time.monotonic() - spawn_t0
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return _abort(reason, detail)

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
    # `new_<sid_token>_sub_<N>.lean`.
    expected_prefix = f"{sid_token}_sub_"
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

    # Dedupe scan: batch-call Lean kernel isDefEq for all candidate
    # sub-goals × eligible ancestors in one subprocess. Hits → write an
    # alias lean file that delegates to canonical via `apply <;>
    # assumption`; insert the alias goal as 'proved' (its proof IS the
    # alias body).
    candidates_for_dedupe: list[tuple[str, str]] = []
    for slug, src in sub_meta:
        try:
            candidates_for_dedupe.append(
                (slug, src.read_text(encoding="utf-8")))
        except OSError:
            candidates_for_dedupe.append((slug, ""))
    canonical_for = dedupe.find_canonicals_batch(
        conn, workspace,
        problem=goal["problem"],
        parent_goal_id=goal_id,
        candidates=candidates_for_dedupe,
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
                content = _ensure_import_mathlib(
                    src.read_text(encoding="utf-8"))
                dest.write_text(content, encoding="utf-8")
            placed.append(dest)
        shutil.copy2(patches[0], scratch_dest)
        placed.append(scratch_dest)

        # F23 — single multi-target lake invocation. Lake's internal
        # scheduler builds independent sub-goal files in parallel and
        # serializes the strategy assembly (which imports the subs)
        # after, replacing the prior serial per-file loop. On a 4-sub
        # strategy the wall-clock dropped from ~5×80s to ~max(80s)+80s.
        # Caller (annotate_failure_detail) smart-truncates stderr to
        # surface error / warning lines.
        ok, err = _lake_build_batch(workspace, placed)
        if not ok:
            raise RuntimeError(f"lake build failed: {err}")

        # F24-A — race guard: between this Backward's dispatch and now
        # (which is up to several minutes due to claude CLI + lake build),
        # an OR-parallel sibling may have shelved or proved this goal.
        # Either way our new strategy is moot. Abort cleanly so cascade
        # has nothing to mutate; clean up sub-goal files we placed.
        # cascade_one's no-op guard handles the same race on its side
        # (defense in depth) — this layer prevents the orphan strategy +
        # sub-goal rows from ever reaching the DB.
        fresh = db.get_goal(conn, goal_id)
        if fresh is None or fresh["status"] not in ("open", "attempting"):
            for p in placed:
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass
            current = fresh["status"] if fresh else "missing"
            return _abort(
                "goal_no_longer_open",
                f"goal {goal_id} transitioned to {current!r} during this "
                f"Backward's run; aborting to avoid orphan strategy.",
                proposal_text,
            )

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
                # F42 — record alias relationship so prune retains the
                # canonical (in case it's an orphan from a dead strategy)
                # for as long as this alias is alive.
                db.set_alias_target(conn, new_gid, canonical_id)
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
        return _abort(
            "lake_build_error",
            diagnostics.annotate_failure_detail(str(exc)),
            proposal_text,
        )


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
