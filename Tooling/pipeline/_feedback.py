"""Agent framework-feedback questionnaire — developer-only writeback.

A dev-mode channel for the framework developer to hear, from the agents
that worked inside the framework, what to improve. Two entry kinds land
in ONE file (`docs/internal/agent_feedback.md`, gitignored):

  1. Survivor self-report — an agent that ran to a resumable terminal
     writes ONE sentence (friction / suggestion / critique) into a scratch
     file in its own sandbox; the framework reads it post-spawn and appends
     a metadata-prefixed line. Piggybacks the reflection spawn (same
     `--resume` session) so it costs no extra spawn. See `_reflection.py`.

  2. Death-cause auto-write — an agent that died without a resumable
     session (the infra reasons `_retry.py` skips reflection for:
     spawn_fast_fail / quota_exhausted / missing_dep) can't self-report,
     so the framework writes its death cause directly. Closes the
     selection bias: the worst experiences would otherwise be invisible.

The agent only ever writes ONE sentence to its own sandbox; the framework
owns the metadata prefix `[ts | kind | model | outcome | problem/slug]` and
the (globally-locked) append to the shared file. So concurrent spawns
across different problems never corrupt the file (each writes its own
sandbox scratch; the framework serializes the appends).

Off by default. Enable with `feedback.enabled: true` in Asterism.yaml (or
`ASTERISM_FEEDBACK_ENABLED=true`). The output file lives under the
gitignored `docs/internal/`, so a shared framework checkout neither has it
nor triggers it.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

_FEEDBACK_REL = "docs/internal/agent_feedback.md"
_SCRATCH_FILENAME = "_agent_feedback.md"

# Standalone framework-feedback questionnaire. Rendered by `attempt_feedback`
# as its OWN `--resume` turn at every pipeline's tail (no longer piggybacked on
# reflection — feedback is decoupled so it covers ALL pipelines uniformly, not
# just the backward/builder reflection). `{feedback_path}` is substituted with
# the survivor scratch path. Framing (per the framework developer): NOT a
# satisfaction survey — ask for the single most useful friction / suggestion /
# critique, grounded; `(none)` only as a genuine last resort.
# Task #10(c): the questionnaire text lives in
# Tooling/prompts/feedback_survivor.md (placeholder __FEEDBACK_PATH__);
# this constant keeps the historical `{feedback_path}` .format contract
# for the render site below.
def _survivor_section() -> str:
    from . import PROMPT_DIR
    return ((PROMPT_DIR / "feedback_survivor.md")
            .read_text(encoding="utf-8").rstrip("\n")
            .replace("__FEEDBACK_PATH__", "{feedback_path}"))


SURVIVOR_PROMPT_SECTION = _survivor_section()
_HEADER = (
    "# Agent framework feedback (dev-only)\n\n"
    "_Survivor self-reports + framework-written death causes. One line each:_\n"
    "_`- [ts | kind | model | outcome | problem/slug] <sentence>`_\n"
    "_(+ optional `  evidence: ...` continuation). Newest at the bottom._\n\n"
)

# Single global lock: the output is ONE shared file across all problems, so
# (unlike LESSONS.md's per-problem lock) appends from concurrent spawns must
# serialize globally. Held only for the fast file append, never across an
# LLM call.
_APPEND_LOCK = threading.Lock()


def feedback_enabled(workspace: Path | None) -> bool:
    """Read `feedback.enabled` from Asterism.yaml / env. Defaults to
    FALSE — this is a developer-only channel, off unless explicitly turned
    on. Accepts "true" / "1" / "yes" / "on" (case-insensitive)."""
    from ..core import config
    raw = config.get(
        "feedback.enabled",
        default=False,
        env_var="ASTERISM_FEEDBACK_ENABLED",
        workspace=workspace,
    )
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "on")


def scratch_path(attempts_dir: Path) -> Path:
    """Where the survivor agent writes its one-sentence answer — inside its
    OWN spawn sandbox, so cross-problem concurrent spawns never contend."""
    return attempts_dir / _SCRATCH_FILENAME


def _resolve_model(kind: str, workspace: Path | None) -> str:
    """The configured model string for `kind` (for the metadata prefix).
    Best-effort: returns '?' if unresolvable."""
    from ..core import config
    try:
        m = config.get(f"{kind.lower()}.model", default="?", workspace=workspace)
        return str(m) if m else "?"
    except Exception:  # noqa: BLE001 — metadata is best-effort
        return "?"


def _append(workspace: Path, line: str) -> None:
    """Globally-locked append of one record to the shared feedback file,
    creating it (with header) on first write. Best-effort: any error is
    swallowed — feedback must never block or fail the dispatcher."""
    path = workspace / _FEEDBACK_REL
    try:
        with _APPEND_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(_HEADER, encoding="utf-8")
            with path.open("a", encoding="utf-8", newline="\n") as f:
                f.write(line if line.endswith("\n") else line + "\n")
    except OSError:
        pass


def _now_minute() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")


def _prefix(*, kind: str, model: str, outcome: str, problem: str,
            slug: str) -> str:
    return (f"- [{_now_minute()} | {kind} | {model} | {outcome} | "
            f"{problem}/{slug}] ")


def record_survivor(workspace: Path | None, *, attempts_dir: Path,
                    kind: str, slug: str, problem: str, outcome: str) -> None:
    """Read the survivor agent's scratch answer and, if it said something,
    append a metadata-prefixed line to the shared file. No-op when feedback
    is disabled, the scratch file is missing/empty, or the answer is the
    explicit `(none)`. Best-effort throughout."""
    if not feedback_enabled(workspace) or workspace is None:
        return
    try:
        sp = scratch_path(attempts_dir)
        if not sp.exists():
            return
        body = sp.read_text(encoding="utf-8").strip()
    except OSError:
        return
    if not body or body.strip().lower() in ("(none)", "none"):
        return
    lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return
    model = _resolve_model(kind, workspace)
    first = lines[0]
    rec = _prefix(kind=kind, model=model, outcome=outcome,
                  problem=problem, slug=slug) + first
    # Carry a single evidence/continuation line if present.
    if len(lines) > 1:
        rec += "\n  " + lines[1].lstrip("- ").strip()
    _append(workspace, rec)


def record_death(workspace: Path | None, *, kind: str, slug: str,
                 problem: str, reason: str) -> None:
    """Framework-written death cause for an agent that died without a
    resumable session (so it can't self-report). No-op when disabled.
    The `(dead)` outcome marker distinguishes these from self-reports."""
    if not feedback_enabled(workspace) or workspace is None:
        return
    rec = _prefix(kind=kind, model=_resolve_model(kind, workspace),
                  outcome="(dead)", problem=problem, slug=slug)
    _append(workspace, rec + f"DIED: {reason} (no resumable session — "
            f"framework-written, agent could not self-report)")


_FEEDBACK_PROMPT_FILENAME = "_feedback_prompt.md"
_FEEDBACK_TIMEOUT_SEC = 90


def attempt_feedback(*, kind: str, sid: str, slug: str, outcome: str,
                     problem_dir: Path, attempts_dir: Path,
                     workspace: Path | None) -> None:
    """Dedicated framework-feedback STEP, run at the tail of every pipeline.

    `--resume <sid>` the just-finished agent session (so the agent answers with
    full context of what it just did — a clean 'looking back' read) and ask the
    standalone questionnaire; then record its one-sentence answer. Uniform
    across pipelines (backward/builder/forward/strategist/librarian-cleanup) so
    framework feedback is no longer limited to the backward/builder reflection.

    No-op when feedback is disabled (so it is FREE in production — only the
    developer's opt-in `feedback.enabled` runs) or `sid` is empty. Best-effort
    throughout: any failure is swallowed — the pipeline outcome already
    committed, a lost feedback turn costs at most one un-recorded sentence."""
    from .. import agent
    if not feedback_enabled(workspace) or not sid:
        return
    try:
        fb_scratch = scratch_path(attempts_dir)
        prompt = SURVIVOR_PROMPT_SECTION.replace("{feedback_path}", str(fb_scratch))
        ppath = attempts_dir / _FEEDBACK_PROMPT_FILENAME
        ppath.write_text(prompt, encoding="utf-8")
        # is_postmortem=True → provider uses `--resume <sid>` and loads the
        # prompt verbatim (same path reflection uses for its resume turn).
        rc = agent.spawn_llm(
            kind=kind, prompt_path=ppath, problem_dir=problem_dir,
            attempts_dir=attempts_dir, session_id=sid,
            is_postmortem=True, timeout_sec=_FEEDBACK_TIMEOUT_SEC)
        wrote = scratch_path(attempts_dir).exists()
        # Diagnostic: the feedback spawn resumes the agent's session via
        # `--resume <sid>`; if that sid is gone / the spawn errors, no scratch
        # is written and the record is silently lost (cleanup:audit / classify
        # produced ZERO entries this way — feedback was wired but never landed).
        # Surface the rc + whether a scratch landed so a dry channel is visible.
        if rc != 0 or not wrote:
            print(f"[feedback] {kind}/{slug}: spawn rc={rc}, "
                  f"scratch_written={wrote} (no record landed)", flush=True)
        record_survivor(workspace, attempts_dir=attempts_dir, kind=kind,
                        slug=slug, problem=problem_dir.name, outcome=outcome)
    except Exception as exc:  # noqa: BLE001 — feedback must never break pipeline
        print(f"[feedback] {kind}/{slug}: raised {type(exc).__name__}: {exc}",
              flush=True)
