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

from .. import agent, db, dedupe, diagnostics, manifest
from ..llm.base import SpawnRC


# P2-#1 regression fix: pipeline.py was converted to pipeline/ package,
# bumping `__file__` one directory deeper. The prompts/ dir lives at
# Tooling/prompts/ — go up one level to reach it. Without this, the
# claude provider silently spawns with an "(prompt file unavailable)"
# stub on every Builder/Backward dispatch (caught by review of
# c398ded — none of the existing tests hit this path because they
# monkeypatch `agent.spawn_llm`).
PROMPT_DIR = Path(__file__).parent.parent / "prompts"

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
    # Hypothesis-direct (handles `A → B → A`-shaped sub-goals where
    # one hypothesis already matches the conclusion verbatim)
    "assumption",
    # Propositional logic
    "tauto",
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
    # Mathlib library search — last because it's the most expensive
    # (queries the discrimination tree across all of Mathlib)
    "exact?",
]


_IMPORT_LINE_RE = re.compile(r"(?m)^import\s")


def _safe_glob(directory: Path, pattern: str) -> list[Path]:
    """Drop-in replacement for `directory.glob(pattern)` that survives
    Windows-reserved characters in sibling filenames.

    `pathlib.Path.glob()` traverses the directory by stat'ing each
    entry; on Windows, `<>:"|?*` in any filename make those stats raise
    `OSError [Errno 22]`, propagating up and killing the entire glob
    even when the bad-named file doesn't match the pattern. Agents
    occasionally write files like `won_exact?.lean` (mistakenly using
    Lean tactic names like `exact?` as identifiers in slugs), and
    `attempts_dir.glob("patch*.lean")` then crashes the whole spawn's
    validation.

    `os.scandir` enumerates raw NTFS entries without per-entry stat;
    `fnmatch.fnmatch` is pure string matching. Together we get the
    pattern semantics without ever resolving the bad-named path.
    """
    import os
    import fnmatch
    out: list[Path] = []
    try:
        with os.scandir(directory) as it:
            for entry in it:
                if fnmatch.fnmatch(entry.name, pattern):
                    out.append(Path(entry.path))
    except OSError:
        pass
    return out


def _ensure_imports_subgoal(
    content: str, *, problem: str, workspace: Path,
) -> str:
    """Prepend `import Mathlib` and `import Problems.<problem>.Defs`
    (when the problem ships a `Defs.lean`) if missing. Idempotent —
    skips any line already present.

    Without `Defs`, problem-level custom symbols (e.g. SG's `Collinear`)
    are unresolved; a strict agent following the prompt's "framework
    auto-injects imports" instruction writes none, and Lean falls back
    to whatever `import Mathlib` exposes (e.g. Mathlib's universe-poly
    `Collinear (k : Type*) ...`), breaking elaboration.
    """
    needed: list[str] = []
    if not re.search(r"(?m)^import\s+Mathlib\b", content):
        needed.append("import Mathlib")
    defs_path = workspace / "Problems" / problem / "Defs.lean"
    if defs_path.exists():
        defs_module = f"Problems.{problem}.Defs"
        if not re.search(rf"(?m)^import\s+{re.escape(defs_module)}\b",
                         content):
            needed.append(f"import {defs_module}")
    if not needed:
        return content
    return "\n".join(needed) + "\n\n" + content


# Recognized values for PROPOSAL.md's `decline_reason` frontmatter field.
# `too_hard` keeps the legacy F48 channel (jump to Backward on same goal);
# `parent_type_infeasible` shelves this goal and cascades up to force the
# parent strategy back into Backward redesign — used when the agent can
# construct a counterexample to the goal under all stated hypotheses, or
# the hypothesis set is missing something the conclusion clearly needs.
DECLINE_TOO_HARD = "too_hard"
DECLINE_PARENT_TYPE_INFEASIBLE = "parent_type_infeasible"
_DECLINE_RE = re.compile(
    r"(?m)^---\s*$.*?^decline_reason\s*:\s*([\w_]+).*?^---\s*$",
    re.DOTALL,
)


def _parse_decline_reason(proposal_text: str) -> str | None:
    """Extract `decline_reason` from PROPOSAL.md YAML frontmatter, if any.

    Returns the raw value (e.g. `'too_hard'` or `'parent_type_infeasible'`),
    or None if the file lacks frontmatter or the field. Unrecognized values
    are returned as-is — caller decides how to dispatch.
    """
    m = _DECLINE_RE.search(proposal_text)
    return m.group(1).strip() if m else None


# `entry_kind: Builder` or `entry_kind: Backward` directive — the
# Backward agent annotates each `new_<slug>.lean` with this comment so
# the framework knows whether to dispatch this sub-goal to Builder
# (one-shot tactic + LLM patch) or skip straight to Backward
# decomposition. Comment-form (not YAML frontmatter) so it sits next to
# the theorem definition the agent is reasoning about.
_ENTRY_KIND_RE = re.compile(
    r"(?m)^\s*--\s*entry_kind\s*:\s*(Builder|Backward)\b"
)


def _parse_entry_kind(lean_text: str) -> str:
    """Extract the `-- entry_kind: ...` directive from a sub-goal lean
    file. Returns 'Builder' or 'Backward' (capitalized as in the DB
    enum); defaults to 'Builder' if the directive is absent or
    unrecognized. The default mirrors the legacy attempts-only routing
    so a missing directive doesn't change behavior."""
    m = _ENTRY_KIND_RE.search(lean_text)
    return m.group(1) if m else "Builder"


@dataclass
class PipelineResult:
    outcome: str  # 'proved' | 'success' | 'exhausted' | 'failed'
    failure_reason: str = ""
    failure_detail: str = ""
    proposal_md: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)


def collect_artifacts(attempts_dir: Path) -> dict[str, str]:
    """Snapshot all .md / .lean / .txt files in attempts_dir for forensic
    preservation in dead_attempts.artifacts JSON column. .txt covers
    `_raw_response.txt` written by the OpenAI provider (raw model output
    before fence parsing) — needed when fence-parse failures point
    blame at the model's output schema.

    P2-#5: promoted from `_collect_artifacts` (used cross-module by
    dispatcher.py)."""
    out: dict[str, str] = {}
    for f in _safe_glob(attempts_dir, "*"):
        if f.suffix not in {".md", ".lean", ".txt"}:
            continue
        try:
            out[f.name] = f.read_text(encoding="utf-8")
        except OSError:
            pass
    return out


# Back-compat alias for any external callers still using the underscore form.
_collect_artifacts = collect_artifacts


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

# P2-#1: lake helpers extracted to _lake.py. Underscore aliases for
# back-compat with existing test + dispatcher imports
# (`pipeline._lake_build`, `pipeline._lean_path_to_module`).
from ._lake import (  # noqa: E402
    lean_path_to_module as _lean_path_to_module,
    lake_build_modules as _lake_build_modules,
    lake_build as _lake_build,
    lake_build_batch as _lake_build_batch,
)


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


# P2-#1: F52 skeleton + alias helpers extracted to _skeleton.py.
# Underscore aliases for back-compat with existing tests.
from ._skeleton import (  # noqa: E402
    signature_prefix as _signature_prefix,
    normalize_signature as _normalize_signature,
    build_strategy_skeleton as _build_strategy_skeleton,
    inject_imports_for_subs as _inject_imports_for_subs,
    verify_backup_path as _verify_backup_path,
    promote_to_alias as _promote_to_alias,
    rollback_promote as _rollback_promote,
)

# F55 — partial-output persistence so a timed-out / failed spawn's
# in-flight work survives into the next attempt's Context.md.
from . import _drafts  # noqa: E402


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


def _attempt_postmortem(*, kind: str, prompt_path: Path,
                        problem_dir: Path, attempts_dir: Path,
                        session_id: str) -> None:
    """F55 — short follow-up spawn after a main-spawn timeout.

    Resumes `session_id` so the killed agent's session memory is
    intact; the postmortem prompt asks the agent to write a brief
    state + blocker note into `attempts_dir/_progress.md`. The wrapper
    around `run_builder` / `run_backward` then captures that file as
    the partial draft for the next dispatch.

    Best-effort: any failure (postmortem also times out, session GC'd,
    provider unavailable) is silently absorbed — the next dispatch
    just cold-starts as it would have without F55. We log the rc to
    the daemon log via the provider's own `[llm:claude] timed out
    after Ns` line; no extra exception path needed.
    """
    try:
        agent.spawn_llm(
            kind=kind,
            prompt_path=prompt_path,
            problem_dir=problem_dir,
            attempts_dir=attempts_dir,
            session_id=session_id,
            is_postmortem=True,
        )
    except Exception:  # noqa: BLE001 — postmortem must not block timeout flow
        pass


def _fetch_last_backward_error(conn: sqlite3.Connection,
                               goal_id: int) -> str:
    """F53 — most recent Backward lake error on this goal. Inlined as
    retry_context so the same-session resume agent sees what its prior
    turn produced + how lake rejected it, without re-reading any
    companion file."""
    row = conn.execute(
        "SELECT da.failure_detail FROM dead_attempts da"
        " JOIN pipelines p ON p.id = da.pipeline_id"
        " WHERE da.target_id = ? AND da.target_kind = 'Goal'"
        "   AND p.kind = 'Backward'"
        " ORDER BY da.id DESC LIMIT 1",
        (goal_id,),
    ).fetchone()
    if row is None or not row["failure_detail"]:
        return ""
    return diagnostics.strip_lake_noise(row["failure_detail"])


def run_builder(conn: sqlite3.Connection, *, goal_id: int,
                workspace: Path, mfst: manifest.Manifest,
                pipeline_id: str) -> PipelineResult:
    """Outer dispatch — runs the inner pipeline then persists or clears
    the partial-output draft (F55) so a future spawn on this same goal
    sees the in-flight patch from the prior failed attempt instead of
    starting from scratch.

    Outcomes:
      - `proved` / `exhausted`: deterministic completion. `exhausted`
        is Phase-1 tactic_try giving up cleanly with no LLM partial to
        preserve; `proved` is the success case. Both clear any prior
        draft (no carry-over wanted).
      - anything else (rc!=0 from spawn, lake_build_error, ...):
        persist whatever the spawn wrote so the next dispatch picks
        up from a sketch.
    """
    goal_row = db.get_goal(conn, goal_id)
    if goal_row is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")
    problem_dir = workspace / "Problems" / goal_row["problem"]
    result = _run_builder_inner(conn, goal_id=goal_id, workspace=workspace,
                                mfst=mfst, pipeline_id=pipeline_id)
    if result.outcome in ("proved", "exhausted"):
        _drafts.clear_partial(problem_dir=problem_dir, kind="builder",
                              goal_id=goal_id)
    else:
        attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
        _drafts.persist_partials(attempts_dir=attempts_dir,
                                 problem_dir=problem_dir,
                                 kind="builder", goal_id=goal_id)
    return result


def _run_builder_inner(conn: sqlite3.Connection, *, goal_id: int,
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
        # P1-#7: mint UUID locally; persist AFTER spawn returns so a
        # process kill mid-spawn leaves DB session_id NULL instead of
        # pointing at a session claude never minted (which would cost
        # one wasted --resume / rc=125 cycle on the next dispatch).
        sid = str(uuid.uuid4())
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

    # P1-#7: persist session_id only after we know spawn completed
    # past the kill window. rc 124/125 paths below clear/replace
    # explicitly; for any other return code claude minted the
    # session and a future retry's --resume can leverage it.
    if not is_retry and rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
        db.set_builder_session_id(conn, goal_id, sid)

    # F33 — fallback for stale session (claude's on-disk session was
    # GC'd or the daemon's DB id outlived the file). One-time retry
    # with a fresh uuid down the cold path.
    if rc == SpawnRC.STALE_SESSION:
        db.set_builder_session_id(conn, goal_id, None)
        sid = str(uuid.uuid4())
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
        if rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
            db.set_builder_session_id(conn, goal_id, sid)

    if rc == SpawnRC.TIMEOUT:
        # Timeout: agent SIGKILL'd mid-write. F55 — before clearing the
        # session id, do a short postmortem spawn that resumes the same
        # session and asks the agent to dump state + blockers into
        # `_progress.md`. The wrapper then captures _progress.md as
        # the partial draft for the next dispatch.
        if sid is not None:
            _attempt_postmortem(
                kind="builder",
                prompt_path=PROMPT_DIR / "builder_postmortem.md",
                problem_dir=workspace / "Problems" / goal["problem"],
                attempts_dir=attempts_dir,
                session_id=sid,
            )
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

    patches = _safe_glob(attempts_dir, "patch*.lean")
    if not patches:
        # F48 — Builder decline channel. The agent followed builder.md's
        # "When to skip writing a patch" hatch: it produced a non-empty
        # PROPOSAL.md explaining why the goal is too hard / needs
        # decomposition, but did not write patch.lean. Cascade treats
        # this distinctly from agent_no_response.
        #
        # `decline_reason` frontmatter sub-routes:
        #   - `parent_type_infeasible` → agent_infeasible (cascade-up:
        #     parent strategy dies, parent goal re-decomposes)
        #   - `too_hard` / missing      → agent_declined  (jump this
        #     goal to Backward via F48 path)
        if proposal_text.strip():
            reason = _parse_decline_reason(proposal_text)
            if reason == DECLINE_PARENT_TYPE_INFEASIBLE:
                return PipelineResult(
                    outcome="failed",
                    failure_reason="agent_infeasible",
                    failure_detail=("builder reports parent type infeasible; "
                                    "PROPOSAL.md must include counterexample"),
                    proposal_md=proposal_text,
                )
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


# F56 — `run_verify` and `_verify_patch_retry` (F41) removed; strategy
# verification is now `Tooling/verify.verify_strategy` (pure framework,
# no LLM) called by `verify.verify_housekeeping` from the dispatcher
# main loop. The legacy LLM-repair path is retired (26 verifies across
# cantor + proj_nonexpansive runs showed 0 Step-1 failures); a future
# regression where lake build at Verify time becomes unreliable can
# re-add it as a separate housekeeping recovery step.


# ---------------------------------------------------------------------
# Backward
# ---------------------------------------------------------------------

def run_backward(conn: sqlite3.Connection, *, goal_id: int,
                 workspace: Path, mfst: manifest.Manifest,
                 pipeline_id: str) -> PipelineResult:
    """Outer dispatch — runs the inner Backward then persists or clears
    the partial-output draft (F55) so a future spawn on this same goal
    sees the in-flight PROPOSAL.md from the prior failed/timed-out
    attempt instead of starting from scratch.

    Outcomes:
      - `success`: strategy committed → clear any prior draft.
      - `failed` with `failure_reason == "goal_no_longer_open"`: the
        race-guard fired because a sibling (re)decomposed or shelved
        this goal mid-spawn. The persisted PROPOSAL.md is moot for any
        future Backward — clear instead of persisting a stale draft
        that would mislead a re-decomposition if the goal later reopens.
      - anything else (rc!=0, parse_proposal_fail, signature mismatch,
        ...): persist what the spawn wrote.
    """
    goal_row = db.get_goal(conn, goal_id)
    if goal_row is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")
    problem_dir = workspace / "Problems" / goal_row["problem"]
    result = _run_backward_inner(conn, goal_id=goal_id, workspace=workspace,
                                 mfst=mfst, pipeline_id=pipeline_id)
    if (result.outcome == "success"
            or result.failure_reason == "goal_no_longer_open"):
        _drafts.clear_partial(problem_dir=problem_dir, kind="backward",
                              goal_id=goal_id)
    else:
        attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
        _drafts.persist_partials(attempts_dir=attempts_dir,
                                 problem_dir=problem_dir,
                                 kind="backward", goal_id=goal_id)
    return result


def _run_backward_inner(conn: sqlite3.Connection, *, goal_id: int,
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

    # F53 — same-session Backward retry (mirror of F33 for Builder).
    # First dispatch on a goal mints a session UUID and pins it via
    # --session-id; subsequent dispatches `claude --resume` so the
    # agent's prior thinking + tool reads + lake-error perception
    # carry over. retry_context inlines the latest lake stderr so the
    # resumed agent sees what its prior turn produced and how lake
    # rejected it.
    import uuid
    sid = db.get_backward_session_id(conn, goal_id)
    is_retry = sid is not None

    # F53/A — reuse the prior dead strategy's id across warm retries.
    # Agent's session memory anchors on the slug it wrote last turn
    # (`L_s152_sub_*`). If this dispatch mints a fresh strategy_id
    # (s153, s154, ...), the resumed agent keeps writing the stale
    # `s152_sub_*` slugs and trips `naming_violation` every time.
    # Pinning sid_token to the prior strategy keeps Context.md, the
    # F52 skeleton, and the agent's session-memory all using the
    # same slug.
    strategy_id: int | None = None
    if is_retry:
        row = conn.execute(
            "SELECT id FROM strategies "
            "WHERE goal_id = ? AND status = 'dead' "
            "ORDER BY id DESC LIMIT 1",
            (goal_id,),
        ).fetchone()
        if row is not None:
            strategy_id = int(row["id"])
            # P0-#3: clear any stale `strategy_subgoals` links from
            # the prior dead cycle. If the previous Backward had
            # committed sub-goals (currently only reachable on full
            # success, which clears session_id and prevents this
            # branch — but defensive against future code paths), the
            # resurrected strategy would otherwise carry ghost links
            # whose subgoal goal-rows are stale. Concretely
            # `strategies_ready_for_verify` checks every linked sub;
            # ghost-but-proved subs would falsely mark the strategy
            # ready for Verify before this Backward had even written
            # the new ones.
            conn.execute(
                "DELETE FROM strategy_subgoals WHERE strategy_id = ?",
                (strategy_id,),
            )
            conn.execute(
                "UPDATE strategies "
                "SET status='proposed', created_by=?, scratch_path='', "
                "    proposal_md='' WHERE id=?",
                (pipeline_id, strategy_id),
            )
            conn.commit()
    if strategy_id is None:
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

    retry_context: str | None = None
    if not is_retry:
        # P1-#7: mint UUID locally; persist AFTER spawn (mirror
        # builder block above).
        sid = str(uuid.uuid4())
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir,
                              strategy_id=strategy_id, kind="backward")
    else:
        retry_context = _fetch_last_backward_error(conn, goal_id)

    # F52 — pre-write strategy patch skeleton: copy parent stub's
    # `theorem <slug> <binders> : <type>` declaration verbatim, rename
    # to `theorem sX`, body = `by sorry`. Agent edits ONLY the body;
    # framework rejects any signature edit via `_signature_prefix` diff.
    # Under F53/A the strategy_id is stable across warm retries, so
    # the skeleton's `theorem sX` head matches both the prior turn's
    # session memory and the current Context.md naming convention.
    parent_abs_for_skeleton = workspace / goal["lean_path"]
    try:
        parent_text = parent_abs_for_skeleton.read_text(encoding="utf-8")
    except OSError as exc:
        return _abort("missing_parent_stub", str(exc))
    namespace = f"Problems.{goal['problem']}"
    skeleton = _build_strategy_skeleton(
        parent_text,
        parent_slug=goal["slug"],
        sid_token=sid_token,
        namespace=namespace,
    )
    if skeleton is None:
        return _abort(
            "parent_stub_not_decomposable",
            f"theorem {goal['slug']} not found in {goal['lean_path']} "
            f"(may have been promoted by a sibling already)",
        )
    skeleton_path = attempts_dir / "patch.lean"
    skeleton_path.write_text(skeleton, encoding="utf-8")
    skeleton_signature = _normalize_signature(
        _signature_prefix(skeleton, sid_token))

    spawn_t0 = time.monotonic()
    rc = agent.spawn_llm(
        kind="backward",
        prompt_path=PROMPT_DIR / "backward.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
        session_id=sid,
        is_retry=is_retry,
        retry_context=retry_context,
    )
    spawn_dur = time.monotonic() - spawn_t0

    # P1-#7: persist after spawn proves session exists.
    if not is_retry and rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
        db.set_backward_session_id(conn, goal_id, sid)

    # F53 — claude session may have been GC'd between dispatches
    # (rc=125). Mint a fresh UUID, recompile context, cold-spawn once.
    if rc == SpawnRC.STALE_SESSION:
        db.set_backward_session_id(conn, goal_id, None)
        sid = str(uuid.uuid4())
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir,
                              strategy_id=strategy_id, kind="backward")
        spawn_t0 = time.monotonic()
        rc = agent.spawn_llm(
            kind="backward",
            prompt_path=PROMPT_DIR / "backward.md",
            problem_dir=workspace / "Problems" / goal["problem"],
            attempts_dir=attempts_dir,
            session_id=sid,
            is_retry=False,
        )
        spawn_dur = time.monotonic() - spawn_t0
        if rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
            db.set_backward_session_id(conn, goal_id, sid)

    if rc == SpawnRC.TIMEOUT:
        # Timeout: agent SIGKILL'd mid-write. F55 — postmortem spawn
        # resumes the killed session for a short state-dump into
        # `_progress.md` before we clear the session id (the wrapper
        # then persists _progress.md as the partial draft).
        if sid is not None:
            _attempt_postmortem(
                kind="backward",
                prompt_path=PROMPT_DIR / "backward_postmortem.md",
                problem_dir=workspace / "Problems" / goal["problem"],
                attempts_dir=attempts_dir,
                session_id=sid,
            )
        db.set_backward_session_id(conn, goal_id, None)
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return _abort(reason, detail)
    if rc != 0:
        # Ordinary failure — keep session_id so the next dispatch's
        # --resume has the prior failed-turn context to learn from.
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return _abort(reason, detail)

    proposal = attempts_dir / "PROPOSAL.md"
    if not proposal.exists():
        return _abort("parse_proposal_fail", "no PROPOSAL.md")
    proposal_text = proposal.read_text(encoding="utf-8")

    patches = _safe_glob(attempts_dir, "patch*.lean")
    new_subs = _safe_glob(attempts_dir, "new_*.lean")
    if not patches or not new_subs:
        # Backward decline channel. Mirrors Builder's F48 hatch: an agent
        # that finds the goal infeasible (counterexample available, or
        # it sees no honest decomposition) writes only PROPOSAL.md with
        # `decline_reason: parent_type_infeasible` — framework cascades
        # up rather than charging another wasted attempt.
        reason = _parse_decline_reason(proposal_text)
        if reason == DECLINE_PARENT_TYPE_INFEASIBLE:
            return _abort(
                "agent_infeasible",
                ("backward reports parent type infeasible; "
                 "PROPOSAL.md must include counterexample"),
                proposal_text,
            )
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

    # F52 — diff check: agent must preserve the framework-locked
    # signature `theorem sX <binders> : <type>`. Whitespace normalized
    # so re-indentation is OK; binder/type changes are not.
    main_patch_text = patches[0].read_text(encoding="utf-8")
    agent_signature = _normalize_signature(
        _signature_prefix(main_patch_text, sid_token))
    if agent_signature != skeleton_signature:
        return _abort(
            "patch_signature_mismatch",
            f"agent edited the locked signature\n"
            f"expected: {skeleton_signature[:300]}\n"
            f"got:      {agent_signature[:300]}",
            proposal_text,
        )

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
                content = _ensure_imports_subgoal(
                    src.read_text(encoding="utf-8"),
                    problem=goal["problem"], workspace=workspace,
                )
                dest.write_text(content, encoding="utf-8")
            placed.append(dest)
        shutil.copy2(patches[0], scratch_dest)
        placed.append(scratch_dest)

        # F52 — auto-inject `import` lines for sub-goal modules into
        # the strategy patch. Agents reliably forget at least one;
        # framework-managed imports avoid an entire class of
        # `unknown identifier` errors at lake build.
        sub_dest_paths = [dest for _, dest in sub_dests]
        _inject_imports_for_subs(workspace, scratch_dest, sub_dest_paths)

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
            entry_kind = _parse_entry_kind(
                dest.read_text(encoding="utf-8"))
            new_gid = db.insert_goal(
                conn, problem=goal["problem"], slug=slug,
                lean_path=rel, statement=stmt, origin="backward",
                depth=goal["depth"] + 1,
                entry_kind=entry_kind,
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
        # F53 — strategy committed; clear backward_session_id so any
        # future Backward on this same goal (e.g. cascade-reopen after
        # a sub-goal shelves) starts from a fresh session rather than
        # resuming a now-stale one talking about a superseded strategy.
        db.set_backward_session_id(conn, goal_id, None)
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
