"""Reflection spawn — agent-curated cross-spawn experience writeback.

After a successful (or terminal-decline) pipeline, the in-pipeline retry
helper still has its sid in scope. We use that sid to fire a brief
`--resume`-based agent spawn that:
  1. reads the current `Problems/<p>/LESSONS.md`,
  2. judges whether THIS attempt exposed a cross-spawn learnable signal,
  3. uses the Edit tool to append (or replace, when at cap) a single
     sentence in LESSONS.md, OR exits silently.

Best-effort. Any failure (timeout, provider error, parse miss) is
swallowed — the primary pipeline outcome already committed; the
reflection's loss is at most one un-saved lesson.

Trigger gating lives in `_retry.py`'s reflection_fn callback wiring;
this module only knows how to RUN the reflection given an sid +
problem context. See `docs/dev/agent_brief_lessons.md` (now archived)
for the design rationale.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .. import agent


_REFLECTION_PROMPT_FILENAME = "_reflection_prompt.md"
_LESSONS_FILENAME = "LESSONS.md"
_REFLECTION_TIMEOUT_SEC = 120

# Per-problem mutex on LESSONS.md edits. Multiple workers can reach
# their pipeline terminals concurrently (different goals, same problem)
# and each fires its own claude reflection spawn that Edit's the same
# file — Edit is read-modify-write, not atomic, so concurrent Edits
# can lose updates or corrupt the file. Serialize per-problem so at
# most one reflection writes LESSONS.md for a given problem at a time.
# In-process lock is sufficient because the dispatcher is single-
# process; multi-process deployments would need an OS-level file lock.
_LESSONS_LOCKS: dict[str, threading.Lock] = {}
_LESSONS_LOCKS_GUARD = threading.Lock()


def _lock_for_problem(problem: str) -> threading.Lock:
    with _LESSONS_LOCKS_GUARD:
        lock = _LESSONS_LOCKS.get(problem)
        if lock is None:
            lock = threading.Lock()
            _LESSONS_LOCKS[problem] = lock
        return lock


def _reflection_enabled(workspace: Path | None) -> bool:
    """Read `lessons.reflection_enabled` from Asterism.yaml / env.
    Defaults to True. Accepts truthy values "true" / "1" / "yes" /
    "on" (case-insensitive). Anything else, including "false" / "0" /
    "no" / "off" / empty, disables reflection.

    Operator emergency switch: set `lessons.reflection_enabled: false`
    in Asterism.yaml (or `ASTERISM_LESSONS_REFLECTION_ENABLED=false` env)
    to disable reflection without redeploying."""
    from .. import config
    raw = config.get(
        "lessons.reflection_enabled",
        default=True,
        env_var="ASTERISM_LESSONS_REFLECTION_ENABLED",
        workspace=workspace,
    )
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "on")


def attempt_reflection(*,
                       kind: str,
                       sid: str,
                       slug: str,
                       outcome: str,
                       problem_dir: Path,
                       attempts_dir: Path,
                       lessons_cap: int,
                       prompt_dir: Path) -> None:
    """Render reflection prompt, spawn agent in `--resume <sid>` mode,
    log a one-line telemetry summary by diffing LESSONS.md before/after.

    Best-effort throughout: any exception is swallowed — the primary
    pipeline outcome is already committed; failed reflection costs at
    most one un-saved lesson, never blocks the dispatcher.
    """
    # Acquire per-problem lock around the entire spawn + diff window.
    # The lock holds for the LLM call duration (~30-90s). Multiple
    # workers reflecting on the same problem serialize here; that's a
    # known cost (the alternative is concurrent Edit which corrupts).
    # Mutually-different problems do not contend.
    lock = _lock_for_problem(problem_dir.name)
    with lock:
        try:
            lessons_path = problem_dir / _LESSONS_FILENAME
            lessons_before = _read_lessons(lessons_path)
            used = _count_lesson_lines(lessons_before)

            template_path = prompt_dir / "reflection.md"
            if not template_path.exists():
                print(f"[reflection] template missing at {template_path}; "
                      f"skipping", flush=True)
                return
            rendered = _render_prompt(
                template_path.read_text(encoding="utf-8"),
                kind=kind, slug=slug, outcome=outcome,
                problem=problem_dir.name,
                cap=str(lessons_cap), used=str(used),
                lessons_content=lessons_before or "(empty)",
                timeout_min=str(max(1, _REFLECTION_TIMEOUT_SEC // 60)),
            )
            rendered_path = attempts_dir / _REFLECTION_PROMPT_FILENAME
            rendered_path.write_text(rendered, encoding="utf-8")

            agent.spawn_llm(
                kind=kind,
                prompt_path=rendered_path,
                problem_dir=problem_dir,
                attempts_dir=attempts_dir,
                session_id=sid,
                # is_postmortem=True borrows the existing "resume + use
                # prompt_path verbatim, no companion file load" path.
                # claude provider handles --resume <sid> already.
                is_postmortem=True,
                timeout_sec=_REFLECTION_TIMEOUT_SEC,
            )

            lessons_after = _read_lessons(lessons_path)
            delta = _classify_delta(lessons_before, lessons_after)
            print(f"[reflection] {kind} {slug}: {delta}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[reflection] {kind} {slug}: error swallowed — {exc}",
                  flush=True)


def _read_lessons(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _count_lesson_lines(content: str) -> int:
    """Count '- <lesson>' bullet lines. Other content (header / blank)
    doesn't count toward the cap."""
    return sum(
        1 for ln in content.splitlines()
        if ln.lstrip().startswith("-")
    )


def _render_prompt(template: str, **kwargs: str) -> str:
    """Simple {field} substitution. Avoids str.format because LESSONS
    content might contain literal `{` characters (e.g. Lean tactic
    blocks)."""
    out = template
    for k, v in kwargs.items():
        out = out.replace("{" + k + "}", v)
    return out


def _classify_delta(before: str, after: str) -> str:
    """One-line telemetry summary of LESSONS.md change. Returns one of:
      'skip'                 — no change
      'wrote (+N lines)'     — agent appended; N lines added
      'replaced (~N lines)'  — agent replaced; line count unchanged but
                               content differs
      'unexpected (B→A)'     — anything else (size shrank without
                               replacement, etc.)
    """
    if before == after:
        return "skip"
    bcount = _count_lesson_lines(before)
    acount = _count_lesson_lines(after)
    if acount > bcount:
        return f"wrote (+{acount - bcount} line)"
    if acount == bcount:
        return f"replaced (~{bcount} lines unchanged count)"
    return f"unexpected (cap shrank {bcount}→{acount})"
