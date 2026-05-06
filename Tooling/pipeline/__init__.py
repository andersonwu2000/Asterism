"""Pipeline package: shared helpers + Builder/Backward dispatch.

Split layout (planned by docs/dev/goal_history_unified.md):
  __init__.py     — shared helpers, constants, common types, re-exports
  builder.py      — `run_builder` + Phase 1/2 logic
  backward.py     — `run_backward` + decomposition + sub-goal placement
  _lake.py        — lake invocation helpers (already split)
  _skeleton.py    — F52 strategy skeleton + alias promotion (already split)
  _drafts.py      — F55 partial-output persistence

Public API surfaced from this module (preserves pre-split callers):
  - run_builder, run_backward                        — dispatch entry points
  - PipelineResult, collect_artifacts                — DTO + forensics
  - _parse_hint_winner                               — Phase 1 hint output parser
  - DECLINE_TOO_HARD, DECLINE_PARENT_TYPE_INFEASIBLE — frontmatter values
  - _drafts                                          — partial-output module

Test-only / dispatcher imports also keep working through underscore
re-exports below (e.g. `pipeline._lake_build`, `pipeline._safe_glob`,
`pipeline._is_sorry_stub`, `pipeline._ensure_imports_subgoal`, etc.).
Integrator atomicity = Hadamard backup-restore (no commit_state).
"""
from __future__ import annotations

import re
import sqlite3
import subprocess  # noqa: F401 — surface for `pipeline.subprocess` monkeypatch in tests
from dataclasses import dataclass, field
from pathlib import Path

from .. import agent, diagnostics


# P2-#1 regression fix: pipeline.py was converted to pipeline/ package,
# bumping `__file__` one directory deeper. The prompts/ dir lives at
# Tooling/prompts/ — go up one level to reach it. Without this, the
# claude provider silently spawns with an "(prompt file unavailable)"
# stub on every Builder/Backward dispatch.
PROMPT_DIR = Path(__file__).parent.parent / "prompts"

# F46 — wall-clock threshold under which a non-zero spawn is reclassified
# as `spawn_fast_fail`. Real claude.exe launches take ~3-5s and the
# fastest legitimate failure (e.g. compilation rejection of malformed
# patch) needs at least one model turn, so 10s is a conservative bound.
# Below this floor, the rc≠0 is almost certainly an infra fault (cwd /
# permission / network / claude.exe crash) rather than agent error.
SPAWN_FAST_FAIL_SEC = 10.0


# ---------------------------------------------------------------------
# DTO + forensic snapshot
# ---------------------------------------------------------------------

@dataclass
class PipelineResult:
    outcome: str  # 'proved' | 'success' | 'failed'
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
    """
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
# Spawn classification
# ---------------------------------------------------------------------

def _spawn_failure(rc: int, attempts_dir: Path,
                   spawn_dur: float) -> tuple[str, str]:
    """Classify a non-zero `agent.spawn_llm` rc into
    (failure_reason, failure_detail). Three classes:

      - `spawn_fast_fail` (F46) — wall-clock < 10s; agent almost
        certainly never ran (claude.exe crashed at startup, prompt
        parser rejected, cwd unreachable, ...). Cascade: no
        goal-attempt increment, dispatcher sets per-target cooldown.
      - `agent_timeout` — rc=124, SIGKILL'd at WORKER_TIMEOUT_SEC.
        Pipeline runs F55 postmortem on this same session before
        returning so next dispatch sees a `.drafts/` progress note.
      - `agent_rc_nonzero` — anything else (rc≠0, wall ≥ 10s,
        rc≠124). Generic agent / spawn error.

    Reads `attempts_dir/_spawn.stderr` (written by the provider on
    rc≠0) and folds the first ~600 chars into failure_detail so
    forensic visibility doesn't depend on grovelling through orphan
    sandbox dirs.
    """
    from ..llm.base import SpawnRC
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
    elif rc == SpawnRC.TIMEOUT:
        reason = "agent_timeout"
    else:
        reason = "agent_rc_nonzero"
    detail = base if not stderr_tail else f"{base}\n{stderr_tail}"
    return reason, detail


# ---------------------------------------------------------------------
# Filesystem / parsing helpers
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Phase 1 — Mathlib `hint` invocation + output parsing
# ---------------------------------------------------------------------

# Phase 1 uses Mathlib's `Mathlib.Tactic.Hint` (`by hint`) instead of a
# framework-maintained tactic list. `hint` runs every tactic registered
# via `register_hint <prio> tac` in priority order, emits a `Try these:`
# info message listing all that succeeded, and uses the first goal-
# closing one as the proof. We parse the info message to recover the
# precise winning tactic and rewrite the patch as `:= by <winner>` for
# a forensically clear final artifact.
#
# Trade-off vs the previous `by first | t1 | t2 | …` design:
#   + Forensic: artifact records the exact winning tactic, not an
#     opaque `first` block.
#   + Coverage: tracks Mathlib's curated hint set automatically (24+
#     tactics; see `register_hint` call sites under
#     `.lake/packages/mathlib/Mathlib/`).
#   + No framework-side list to maintain.
#   - Cost: 2 lake builds on success (probe + confirm) instead of 1.
#     In practice the second build hits warm cache for almost everything
#     except the swapped tactic body.
#   - Coverage gap: a few legacy TACTIC_TRY_LIST entries (rfl,
#     assumption, norm_cast, ring_nf, simp, nlinarith) are not
#     register_hint'd in Mathlib's defaults; goals that only those
#     close fall through to Phase 2.

# Output format (from Mathlib/Tactic/Hint.lean + lake build observation):
#     info: <file>:<line>:<col>: Try these:
#       [apply] 🎉️ <tactic that closed the goal>      ← winner
#       [apply] <tactic that left subgoals>           ← non-winner, skip
# Failure: rc != 0 + "error: No suggestions available".
_HINT_WINNER_RE = re.compile(
    r"^\s*\[apply\]\s*🎉️\s*(.+?)\s*$", re.MULTILINE
)


def _parse_hint_winner(output: str) -> str | None:
    """First 🎉️-marked tactic from `hint`'s `Try these:` block, or None.

    The 🎉️ marker is added by `Mathlib.Tactic.Hint.suggestion` only
    when the candidate tactic closed all goals. `hint` orders by
    `register_hint` priority desc, so the first 🎉️ entry is the
    highest-priority successful close — the same tactic `hint` itself
    used to seal the proof.
    """
    m = _HINT_WINNER_RE.search(output)
    return m.group(1).strip() if m else None


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


# ---------------------------------------------------------------------
# Decline frontmatter
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# Cross-pipeline helpers
# ---------------------------------------------------------------------

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


def _slug_from_filename(name: str) -> str:
    """`new_<slug>.lean` → `<slug>` (Backward sub-goal placement)."""
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


# ---------------------------------------------------------------------
# Re-exports from sub-modules (must come AFTER helper defs above so
# late-imports inside builder.py / backward.py find them ready).
# ---------------------------------------------------------------------

# Lake invocation helpers (P2-#1 split).
from ._lake import (  # noqa: E402
    lean_path_to_module as _lean_path_to_module,
    lake_build_modules as _lake_build_modules,
    lake_build as _lake_build,
    lake_build_batch as _lake_build_batch,
)

# F52 skeleton + alias helpers (P2-#1 split).
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

# Pipeline-specific helpers (split; re-exported for tests / dispatcher
# that import via `pipeline.<name>`).
from .backward import (  # noqa: E402
    _ensure_imports_subgoal,
    _try_promote_sorry_free,
    _parse_entry_kind,
    _SORRY_RE,
    run_backward,
)
from .builder import run_builder  # noqa: E402
