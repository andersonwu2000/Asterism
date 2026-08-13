"""Standard spawn-lifecycle hooks for goal-targeted pipelines (task #8).

Builder and Backward wired the same four hooks (postmortem / reflection /
feedback / death) in ~45 near-verbatim lines each; a future gate or hook
change had to be applied twice and could silently drift. One factory now
owns the shape; Forward keeps its own two hooks (different slug identity,
deliberately no reflection/death) — it was never a copy of this pack.
"""
from __future__ import annotations

from pathlib import Path


def make_goal_hooks(*, kind: str, seat: str, goal, problem_dir: Path,
                    attempts_dir: Path, prompt_dir: Path,
                    workspace: Path, postmortem_prompt: Path):
    """The (postmortem_fn, reflection_fn, feedback_fn, death_fn) tuple for
    a goal-targeted pipeline spawn. `goal` is the sqlite goal row (slug /
    id / problem).

    `kind` NAMES the record (log lines, `agent_feedback.md`, death rows).
    `seat` DISPATCHES.
    THE SEAT, NOT THE LABEL. A tail turn RESUMES the session the work
    spawn minted, so it must be dispatched with the same seat the work
    spawn used — otherwise the provider lookup lands somewhere else and
    the resume is handed a session id that provider never issued.
    Measured 2026-08-13: the mint arm labels its tail `forward`, a seat
    retired in the Formalizer merge, so `forward.provider` fell back to
    the default and `claude --resume <codex-session-id>` returned rc=1
    on four consecutive runs — silent on an all-claude setup, where
    both names happen to resolve to the same provider.
    """

    def postmortem_fn(sid: str) -> None:
        from . import _attempt_postmortem
        _attempt_postmortem(
            seat=seat, prompt_path=postmortem_prompt,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid)

    def reflection_fn(sid: str, result) -> None:
        from ._reflection import attempt_reflection, _reflection_enabled
        if not _reflection_enabled(workspace):
            return
        attempt_reflection(
            kind=kind, seat=seat, sid=sid, slug=goal["slug"],
            outcome=(result.failure_reason or result.outcome),
            goal_id=int(goal["id"]), problem=str(goal["problem"]),
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            prompt_dir=prompt_dir, workspace=workspace)

    def feedback_fn(sid: str, result) -> None:
        from . import _feedback
        _feedback.attempt_feedback(
            kind=kind, seat=seat, sid=sid, slug=goal["slug"],
            outcome=(result.failure_reason or result.outcome),
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            workspace=workspace)

    def death_fn(result) -> None:
        from . import _feedback
        _feedback.record_death(
            workspace, kind=kind, slug=goal["slug"],
            problem=problem_dir.name,
            reason=result.failure_reason or result.outcome)

    return postmortem_fn, reflection_fn, feedback_fn, death_fn
