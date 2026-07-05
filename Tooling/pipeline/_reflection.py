"""Reflection spawn — agent-curated cross-spawn experience writeback (Model B).

After a successful (or terminal-decline) pipeline, the in-pipeline retry
helper still has its sid in scope. We use that sid to fire a brief
`--resume`-based agent spawn that picks ONE of:
  * `skip`         — no cross-goal-transferable signal (the dominant case),
  * `global_add`   — a problem-wide insight that helps OTHER goals,
  * `global_edit`  — correct / supersede an existing global insight (C3-A).

GLOBAL-ONLY (2026-06-28): node-bound lessons were retired. A stress test
(green_theorem, 70 goals) showed node lessons have ~zero cross-goal value —
47/51 were goal-specific decomposition recipes, useless to any other goal —
and their only cross-goal delivery path (a grep-able file) was exercised by
~1% of worker spawns. The cross-goal value lives entirely in the small set of
GLOBAL lessons, which workers DO consume (inlined into Context.md, read by
94%). So reflection now writes only globals; a goal-specific takeaway is a
`skip`. (An old-prompt `node` decision falls through to skip harmlessly.)

The agent writes its choice to a `_reflection_decision.json` sentinel; the
framework parses it and writes straight to the KB (`kb_entries`) — the KB is
the source of truth, the old flat `LESSONS.md` mirror is gone.

Best-effort. Any failure (timeout, provider error, parse miss, no decision
file) is swallowed — the primary pipeline outcome already committed; the
reflection's loss is at most one un-saved lesson.

Trigger gating lives in `_retry.py`'s reflection_fn callback wiring;
this module only knows how to RUN the reflection given an sid + goal context.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .. import agent
from ..state import db, kb


_REFLECTION_PROMPT_FILENAME = "_reflection_prompt.md"
_RETRACT_SENTINEL_FILENAME = "_directive_retract.md"
_DECISION_FILENAME = "_reflection_decision.json"
_REFLECTION_TIMEOUT_SEC = 120

# Per-problem mutex on the reflection read-globals → decide → write window.
# Multiple workers can reach their pipeline terminals concurrently (different
# goals, same problem) and each fires its own reflection spawn. Serializing
# per-problem keeps each spawn's dedup decision (does an equivalent global
# already exist?) consistent against a stable picture, and avoids two spawns
# racing a global edit. In-process lock suffices — the dispatcher is single-
# process; multi-process deployments would need an OS-level lock.
_REFLECTION_LOCKS: dict[str, threading.Lock] = {}
_REFLECTION_LOCKS_GUARD = threading.Lock()


def _lock_for_problem(problem: str) -> threading.Lock:
    with _REFLECTION_LOCKS_GUARD:
        lock = _REFLECTION_LOCKS.get(problem)
        if lock is None:
            lock = threading.Lock()
            _REFLECTION_LOCKS[problem] = lock
        return lock


def _reflection_enabled(workspace: Path | None) -> bool:
    """Read `lessons.reflection_enabled` from Asterism.yaml / env.
    Defaults to True. Accepts truthy values "true" / "1" / "yes" /
    "on" (case-insensitive). Anything else, including "false" / "0" /
    "no" / "off" / empty, disables reflection.

    Operator emergency switch: set `lessons.reflection_enabled: false`
    in Asterism.yaml (or `ASTERISM_LESSONS_REFLECTION_ENABLED=false` env)
    to disable reflection without redeploying."""
    from ..core import config
    raw = config.get(
        "lessons.reflection_enabled",
        default=True,
        env_var="ASTERISM_LESSONS_REFLECTION_ENABLED",
        workspace=workspace,
    )
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes", "on")


def _read_directive(problem: str) -> str:
    """Current `problems.strategist_directive` for the problem ('' if none /
    on any error — best-effort, never raises)."""
    try:
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT strategist_directive FROM problems WHERE name = ?",
                (problem,),
            ).fetchone()
            return (str(row["strategist_directive"]) if row
                    and row["strategist_directive"] else "")
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — best-effort
        return ""


def _clear_directive(problem: str) -> None:
    """Retract the standing directive (C3-A): the reflection agent flagged it
    as disproved by this attempt. Clear-only — the Strategist owns the content
    and re-issues a corrected directive on its next wake; an absent directive
    beats a wrong one. NO Strategist enqueue (no extra spawn)."""
    conn = db.connect()
    try:
        db.set_problem_strategist_directive(conn, problem, None)
        conn.commit()
    finally:
        conn.close()


def attempt_reflection(*,
                       kind: str,
                       sid: str,
                       slug: str,
                       outcome: str,
                       goal_id: int,
                       problem: str,
                       problem_dir: Path,
                       attempts_dir: Path,
                       prompt_dir: Path,
                       workspace: Path | None = None) -> None:
    """Render reflection prompt, spawn agent in `--resume <sid>` mode, then
    apply the agent's `_reflection_decision.json` choice straight to the KB.

    Best-effort throughout: any exception is swallowed — the primary pipeline
    outcome is already committed; failed reflection costs at most one un-saved
    lesson, never blocks the dispatcher.
    """
    # Hold the per-problem lock across the whole read-globals → spawn → write
    # window (~30-90s) so each spawn's dedup sees a stable picture.
    #
    # `problem` is the FULL registered name (e.g. 'Geometry.foo'); never use
    # `problem_dir.name`, which is the leaf ('foo') for namespaced problems —
    # the KB / `problems(name)` FK + directive lookups all key on the full
    # name, so the leaf silently breaks every namespaced problem.
    lock = _lock_for_problem(problem)
    with lock:
        try:
            # Surface the existing GLOBAL lessons (with ids) so the agent can
            # dedup before a global_add or pick an id for global_edit.
            conn = db.connect()
            try:
                existing_globals = kb.global_lessons(conn, problem)
            finally:
                conn.close()

            # C3-A: surface the standing directive so reflection can retract it
            # if THIS outcome disproved a concrete claim it makes.
            directive = _read_directive(problem)

            # Clear any stale sentinels from a prior spawn before this one runs.
            decision_path = attempts_dir / _DECISION_FILENAME
            retract_sentinel = attempts_dir / _RETRACT_SENTINEL_FILENAME
            for p in (decision_path, retract_sentinel):
                try:
                    p.unlink()
                except OSError:
                    pass

            template_path = prompt_dir / "_shared" / "reflection.md"
            if not template_path.exists():
                print(f"[reflection] template missing at {template_path}; "
                      f"skipping", flush=True)
                return
            # Framework feedback is DECOUPLED from reflection — it runs as its
            # own `--resume` step (`_feedback.attempt_feedback`) at every
            # pipeline's tail, so reflection here is KB-lessons-only.
            rendered = _render_prompt(
                template_path.read_text(encoding="utf-8"),
                kind=kind, slug=slug, outcome=outcome, problem=problem,
                goal_id=str(goal_id),
                global_lessons=_render_globals(existing_globals),
                directive=directive or "(no standing directive)",
                decision_path=str(decision_path),
                attempts_dir=str(attempts_dir),
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
                is_postmortem=True,
                timeout_sec=_REFLECTION_TIMEOUT_SEC,
            )

            # C3-A: honor a directive-retraction sentinel the agent wrote
            # (only meaningful when a directive was actually standing).
            if directive and retract_sentinel.exists():
                try:
                    reason = retract_sentinel.read_text(
                        encoding="utf-8").strip()
                except OSError:
                    reason = ""
                _clear_directive(problem)
                print(f"[reflection] {kind} {slug}: retracted strategist "
                      f"directive — {reason[:160]}", flush=True)

            # Apply the agent's KB decision (skip / global_add / global_edit).
            # Best-effort; a KB hiccup must not lose telemetry.
            try:
                delta = _apply_decision(problem, goal_id, sid, decision_path)
            except Exception as exc:  # noqa: BLE001
                delta = f"decision skipped — {exc}"
            print(f"[reflection] {kind} {slug}: {delta}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[reflection] {kind} {slug}: error swallowed — {exc}",
                  flush=True)


def _render_globals(rows: list[sqlite3.Row]) -> str:
    """Render existing global lessons as an id-tagged TITLES-ONLY list for
    the prompt, so the agent can dedup (global_add only when not already
    present) and target a global_edit by id.

    Titles-only (2026-07-05, twin of the worker-context titles index): the
    full-body render grew past 30KB on sphere_homology and — inlined into
    the `-p` command line — blew the Windows 32,767-char CreateProcess cap
    (WinError 206), silently killing every reflection. Titles are the
    actionable one-liners by this prompt's own design; dedup/edit judgment
    reads them, not the elaboration."""
    if not rows:
        return "(none yet)"
    return "\n".join(f"- [id {r['id']}] {(r['title'] or '').strip()}"
                     for r in rows)


def _apply_decision(problem: str, goal_id: int, sid: str,
                    decision_path: Path) -> str:
    """Parse `_reflection_decision.json` and apply it to the KB. Returns a
    one-line telemetry string. Never raises on a missing / malformed file —
    that just reads as a skip."""
    if not decision_path.exists():
        return "skip (no decision)"
    try:
        data = json.loads(decision_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"skip (unparseable decision: {exc})"
    if not isinstance(data, dict):
        return "skip (decision not an object)"

    action = str(data.get("action", "skip")).strip().lower()
    if action == "skip":
        return "skip"
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    # One write per spawn (the actions are mutually exclusive), so the sid is a
    # stable idempotency key: a re-fired spawn re-applies without duplicating.
    provenance = f"reflection:{sid}"

    conn = db.connect()
    try:
        if action == "global_add":
            if not title:
                return "skip (global_add: empty title)"
            n = kb.add_lesson(conn, problem=problem, title=title, body=body,
                              node_id=None, provenance=provenance)
            return f"global add ({'wrote' if n else 'dup'})"
        if action == "global_edit":
            try:
                entry_id = int(data.get("id"))
            except (TypeError, ValueError):
                return "skip (global_edit: bad id)"
            if not title:
                return "skip (global_edit: empty title)"
            n = kb.edit_global_lesson(conn, entry_id=entry_id, problem=problem,
                                      title=title, body=body)
            return f"global edit id={entry_id} ({'ok' if n else 'no-match'})"
        return f"skip (unknown action {action!r})"
    finally:
        conn.close()


def _render_prompt(template: str, **kwargs: str) -> str:
    """Simple {field} substitution. Avoids str.format because lesson content
    might contain literal `{` characters (e.g. Lean tactic blocks)."""
    out = template
    for k, v in kwargs.items():
        out = out.replace("{" + k + "}", v)
    return out
