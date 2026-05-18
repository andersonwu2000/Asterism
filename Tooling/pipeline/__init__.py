"""Pipeline package: shared helpers + Builder/Backward dispatch.

Split layout (planned by docs/dev/goal_history_unified.md):
  __init__.py     — shared helpers, constants, common types, re-exports
  builder.py      — `run_builder` + Phase 1/2 logic
  backward.py     — `run_backward` + decomposition + sub-goal placement
  _lake.py        — lake invocation helpers (already split)
  _skeleton.py    — strategy skeleton + alias promotion (already split)
  _drafts.py      — partial-output persistence

Public API surfaced from this module (preserves pre-split callers):
  - run_builder, run_backward                        — dispatch entry points
  - PipelineResult, collect_artifacts                — DTO + forensics
  - _parse_hint_winner                               — Phase 1 hint output parser
  - DECLINE_*, DECLINE_DIRECTIVES, DECLINE_TO_FAILURE_REASON — unified
                                                       decline vocabulary
                                                       (see docs/archive/decline_directives.md)
  - _extract_leading_comments, _extract_decline_reason — Phase 6 parsing
  - _drafts                                          — partial-output module

Test-only / dispatcher imports also keep working through underscore
re-exports below (e.g. `pipeline._lake_build`, `pipeline._safe_glob`,
`pipeline._is_sorry_stub`, `pipeline._ensure_imports_subgoal`, etc.).
Integrator atomicity = Hadamard backup-restore (no commit_state).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess  # noqa: F401 — surface for `pipeline.subprocess` monkeypatch in tests
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .. import agent
from ..quality import diagnostics


def _write_mcp_config(attempts_dir: Path, workspace: Path,
                      target: Path, *,
                      pipeline_id: str, problem: str) -> Path:
    """Generate the MCP config JSON claude CLI uses to connect to the
    long-living gateway. One HTTP MCP server per daemon; spawns
    connect over HTTP with a session token in the
    `X-Asterism-Session` header. The token is obtained by POST to
    `/register` immediately before writing this file; the gateway
    associates the token with `target` so tool calls operate on the
    right file.
    """
    import urllib.request as _u
    import urllib.error as _ue
    config_path = attempts_dir / "_mcp_config.json"
    log_path = attempts_dir / "_mcp.jsonl"
    token_file = attempts_dir / "_gateway_session.token"
    from ..core import config as _cfg
    gateway_port = _cfg.get(
        "gateway.port", default=8765,
        env_var="ASTERISM_GATEWAY_PORT", cast=int,
        workspace=workspace,
    )
    base = f"http://127.0.0.1:{gateway_port}"

    # Release any leftover session from a prior retry on this pipeline.
    # Each warm retry calls back into here; without release the gateway
    # accumulates open files on the shared backend (gradual mem leak).
    if token_file.exists():
        old_token = token_file.read_text(encoding="utf-8").strip()
        if old_token:
            try:
                rel = _u.Request(f"{base}/release/{old_token}",
                                 method="POST")
                _u.urlopen(rel, timeout=5.0).read()
            except (_ue.URLError, OSError):
                pass

    register_body = json.dumps({
        "pipeline_id": pipeline_id,
        "target_path": str(target),
        "problem": problem,
        "workspace": str(workspace),
        "log_path": str(log_path),
    }).encode("utf-8")
    req = _u.Request(base + "/register", data=register_body,
                     headers={"Content-Type": "application/json"},
                     method="POST")
    with _u.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
    payload = json.loads(body)
    token = payload.get("session_token")
    if not token:
        raise RuntimeError(
            f"gateway /register returned no session_token: {body}")

    config = {
        "mcpServers": {
            "lsp": {
                "type": "http",
                "url": f"{base}/mcp",
                "headers": {"X-Asterism-Session": token},
            },
        },
    }
    config_path.write_text(json.dumps(config, indent=2),
                           encoding="utf-8")
    # Also store the token in attempts_dir so the framework can
    # POST /release/{token} when the spawn completes (cleanup hook).
    (attempts_dir / "_gateway_session.token").write_text(
        token, encoding="utf-8")
    return config_path


# Regression fix from the pipeline.py → pipeline/ package split: that
# bumped `__file__` one directory deeper. The prompts/ dir lives at
# Tooling/prompts/ — go up one level to reach it. Without this, the
# claude provider silently spawns with an "(prompt file unavailable)"
# stub on every Builder/Backward dispatch.
PROMPT_DIR = Path(__file__).parent.parent / "prompts"

# Wall-clock threshold under which a non-zero spawn is reclassified
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
    outcome: str  # 'proved' | 'success' | 'failed' | 'exhausted' | 'moot'
    failure_reason: str = ""
    failure_detail: str = ""
    proposal_md: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)
    # Phase 7 — per-retry failure records buffered by the in-pipeline
    # retry helper. The helper cannot INSERT dead_attempts during the
    # loop because the pipelines row (FK target) is written by
    # `_run_pipeline` only after this PipelineResult returns. Caller
    # (`dispatcher._run_pipeline`) flushes these after the pipelines
    # INSERT: one `dead_attempts` row + one `goals.attempts++` per
    # entry, preserving the 1:1 invariant (decision 5/6).
    # Each entry has keys: reason, detail, proposal_md, artifacts.
    pending_failures: list[dict] = field(default_factory=list)


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


# ---------------------------------------------------------------------
# Spawn classification
# ---------------------------------------------------------------------

def _spawn_failure(rc: int, attempts_dir: Path,
                   spawn_dur: float) -> tuple[str, str]:
    """Classify a non-zero `agent.spawn_llm` rc into
    (failure_reason, failure_detail). Three classes:

      - `spawn_fast_fail` — wall-clock < 10s; agent almost certainly
        never ran (claude.exe crashed at startup, prompt parser
        rejected, cwd unreachable, ...). Cascade: no goal-attempt
        increment, dispatcher sets per-target cooldown.
      - `agent_timeout` — rc=124, SIGKILL'd at WORKER_TIMEOUT_SEC.
        Pipeline runs a postmortem on this same session before
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
    if rc == SpawnRC.TIMEOUT:
        # rc=124 is unambiguous: SIGKILL at WORKER_TIMEOUT_SEC. The
        # wall-clock check below cannot apply (timeout is several
        # minutes); this ordering also defends against artificial
        # spawn_dur values in unit tests.
        reason = "agent_timeout"
    elif spawn_dur < SPAWN_FAST_FAIL_SEC:
        base = f"agent rc={rc} (fast-fail in {spawn_dur:.1f}s)"
        reason = "spawn_fast_fail"
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
#   - Coverage gap: a few common tactics (rfl, assumption, norm_cast,
#     ring_nf, simp, nlinarith) are not in Mathlib's `register_hint`
#     defaults; goals that only those close fall through to Phase 2.

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
# Decline directives (unified vocabulary, see docs/archive/decline_directives.md)
# ---------------------------------------------------------------------

# Recognized values for the `-- decline: <directive>` directive an
# agent writes at the top of patch.lean to opt out of the success
# path. Routing semantics live in cascade_one; description (the
# agent's `## ...` block under the directive) is preserved in
# dead_attempts.proposal_md and projected to downstream context.
#
#   unprovable          — false in this hypothesis scope; description
#                         must give a counterexample.  Persisted as
#                         failure_reason='agent_infeasible' (legacy).
#   return_to_parent    — provable after parent strategy is fixed;
#                         description must name the fix.  Cascades up
#                         to parent re-decompose with description as
#                         fix hint.  failure_reason='parent_needs_fix'.
#   shelve              — lacks math tools / scaffolding to proceed;
#                         description must name needed Forward lemma
#                         statements / supporting defs / theorems.
#                         Cascade routes to pending_strategist_review;
#                         Strategist decides next move (Inject Forward
#                         with the agent's brief / ConfirmShelve /
#                         Reopen with directive).
#                         failure_reason='agent_shelved'.
#   needs_decomposition — Builder-only; routes to Backward via
#                         entry_kind switch (legacy too_hard channel).
#                         failure_reason='agent_declined'.
DECLINE_UNPROVABLE = "unprovable"
DECLINE_RETURN_TO_PARENT = "return_to_parent"
DECLINE_SHELVE = "shelve"
DECLINE_NEEDS_DECOMPOSITION = "needs_decomposition"

# Set of every recognized directive (parser uses for membership check;
# unknown directives fall through to the generic `agent_declined`
# branch downstream).
DECLINE_DIRECTIVES = frozenset({
    DECLINE_UNPROVABLE,
    DECLINE_RETURN_TO_PARENT,
    DECLINE_SHELVE,
    DECLINE_NEEDS_DECOMPOSITION,
})

# Map directive → DB failure_reason. Keeps existing enum values for
# unprovable / needs_decomposition (no schema migration needed); adds
# two new values for the new directives.
DECLINE_TO_FAILURE_REASON = {
    DECLINE_UNPROVABLE: "agent_infeasible",
    DECLINE_RETURN_TO_PARENT: "parent_needs_fix",
    DECLINE_SHELVE: "agent_shelved",
    DECLINE_NEEDS_DECOMPOSITION: "agent_declined",
}


# ---------------------------------------------------------------------
# Cross-pipeline helpers
# ---------------------------------------------------------------------

def _attempt_postmortem(*, kind: str, prompt_path: Path,
                        problem_dir: Path, attempts_dir: Path,
                        session_id: str) -> None:
    """Short follow-up spawn after a main-spawn timeout.

    Resumes `session_id` so the killed agent's session memory is
    intact; the postmortem prompt asks the agent to write a brief
    state + blocker note into `attempts_dir/_progress.md`. The wrapper
    around `run_builder` / `run_backward` then captures that file as
    the partial draft for the next dispatch.

    Best-effort: any failure (postmortem also times out, session GC'd,
    provider unavailable) is silently absorbed — the next dispatch
    just cold-starts as it would have without postmortem persistence.
    We log the rc to the daemon log via the provider's own
    `[llm:claude] timed out after Ns` line; no extra exception path
    needed.
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


_THEOREM_DECL_RE = re.compile(r"^\s*theorem\s+\S+", re.MULTILINE)


def _extract_leading_comments(text: str) -> str:
    """Return all `--` comment lines that appear before the first
    `theorem` declaration in a Lean source, in source order. Imports,
    namespace lines, blank lines, and other non-`--` lines that
    intersperse with comments are skipped — they're framework /
    boilerplate, not the agent's annotation.

    Captures both placements agents naturally use:
      * file-top docstring (above imports), and
      * Mathlib-style doc-comment immediately preceding the theorem
        (after `namespace ...` etc).

    Blank lines that fall *between* two captured comment lines are
    preserved as bare `--` paragraph separators; pure-blank lines from
    the boilerplate region are dropped. Empty result if the file has
    no comments before the theorem (or no theorem at all).

    Phase 6 single-output design: this block is the agent's annotation
    source (Builder success summary / Backward strategy rationale /
    `-- decline: <reason>` directive).
    """
    m = _THEOREM_DECL_RE.search(text)
    upper_bound = m.start() if m else len(text)
    region = text[:upper_bound]
    out: list[str] = []
    buffered_blanks: list[str] = []
    for ln in region.splitlines(keepends=True):
        stripped = ln.strip()
        if stripped.startswith("--"):
            if buffered_blanks:
                out.extend(buffered_blanks)
                buffered_blanks = []
            out.append(ln)
        elif stripped == "":
            if out:
                buffered_blanks.append(ln)
            # else: blank in the boilerplate region before any comment → drop
        # else: import / namespace / open / etc — skip without breaking
    return "".join(out)


_DECLINE_DIRECTIVE_RE = re.compile(r"^\s*--\s*decline\s*:\s*(\S+)",
                                   re.MULTILINE)


def _extract_decline_reason(comment_block: str) -> str | None:
    """If the leading comment block opens with a `-- decline: <reason>`
    directive, return the reason. Otherwise None. The directive must
    appear in the leading-comment region (caller already extracted via
    `_extract_leading_comments`); placing it deeper in the file is
    ignored on purpose so an agent describing prior declines in a
    paragraph can't accidentally trigger the path.
    """
    m = _DECLINE_DIRECTIVE_RE.search(comment_block)
    return m.group(1) if m else None


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

# Lake invocation helpers (split out of this package).
from ._lake import (  # noqa: E402
    lean_path_to_module as _lean_path_to_module,
    lake_build_modules as _lake_build_modules,
    lake_build as _lake_build,
    lake_build_batch as _lake_build_batch,
)

# Strategy skeleton + alias helpers (split out of this package).
from ._skeleton import (  # noqa: E402
    signature_prefix as _signature_prefix,
    normalize_signature as _normalize_signature,
    build_strategy_skeleton as _build_strategy_skeleton,
    inject_imports_for_subs as _inject_imports_for_subs,
    verify_backup_path as _verify_backup_path,
    promote_to_alias as _promote_to_alias,
    rollback_promote as _rollback_promote,
)

# Partial-output persistence so a timed-out / failed spawn's
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
