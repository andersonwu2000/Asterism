"""Per-pipeline progress-note persistence (F55).

When a worker spawn times out, the framework does a short follow-up
"postmortem" spawn (`agent.spawn_llm(is_postmortem=True)`) that
resumes the killed session and asks the agent to write a brief
state-and-blocker note into `attempts_dir/_progress.md`. This module
captures that note and persists it to a stable per-(kind, goal) file
under `problem_dir/.drafts/<kind>_g<gid>.md`, so the NEXT regular
spawn's Context.md can surface it. Cleared on pipeline success.

Motivation: sylvester_gallai Backward root spawn timed out 3× at 600s
and 2× at 720s without producing PROPOSAL.md, because Sonnet needed
> 12 min to compose a Kelly-minimiser decomposition end-to-end. The
session memory of each killed spawn carried plenty of useful thinking
(decomposition sketch, identified Mathlib lemmas, blocking points)
but the prior design discarded it. The postmortem spawn extracts that
state into a short note before the session is lost.

Why not "save PROPOSAL incrementally" (the original F55 design):
- Pollutes the agent's attention budget — agent has to maintain a
  growing deliverable in parallel with thinking.
- Encourages premature commitment to a decomposition shape that
  becomes hard to revise mid-spawn.
- Relies on the agent's self-discipline to save at the right moments.
The postmortem-spawn design moves the burden to the framework: main
spawn is uninterrupted thinking; the post-kill recap is a separate,
narrowly-scoped LLM call.

attempts_dir is per-spawn (random uuid path); `.drafts/` is per-(kind,
goal) so the carry-over is stable across spawns. `.drafts/` lives
inside `problem_dir`, so it's covered by the existing F44 sandbox + M1
allowlist — no separate add-dir needed.
"""
from __future__ import annotations

from pathlib import Path

# kind → filenames in attempts_dir to capture as the partial output.
# Both kinds use `_progress.md`, written by the postmortem-spawn agent
# (see `Tooling/prompts/<kind>_postmortem.md`). Kept as a one-line dict
# so future agent kinds (Strategist, Forward, ...) can opt in.
PARTIAL_PERSIST: dict[str, list[str]] = {
    "backward": ["_progress.md"],
    "builder":  ["_progress.md"],
}

# Per-file char cap when persisting + inlining. Sized so the partial
# section in Context.md stays tight ("agent 看到的資訊要清楚簡潔");
# `_progress.md` is bounded by the postmortem prompt (~150 words target),
# so the cap is a hard backstop more than a typical-case constraint.
PARTIAL_BUDGETS: dict[str, int] = {
    "backward": 2000,
    "builder":  2000,
}
# Back-compat for callers that don't pass `kind`.
PARTIAL_BUDGET = 2000


def drafts_path(problem_dir: Path, kind: str, goal_id: int) -> Path:
    return problem_dir / ".drafts" / f"{kind}_g{goal_id}.md"


def persist_partials(*, attempts_dir: Path, problem_dir: Path,
                     kind: str, goal_id: int) -> Path | None:
    """Capture kind's partial outputs from `attempts_dir` into the
    per-goal drafts file. Idempotent — overwrites any prior draft so the
    most recent attempt's draft is what next spawn sees. Returns the
    drafts path on write, None when nothing was captured (no source
    files, all empty, or unknown kind).
    """
    sources = PARTIAL_PERSIST.get(kind)
    if not sources:
        return None
    # Nit-fix from F55 review: tolerate missing attempts_dir (early
    # `goal_not_found` / `lean_file_missing` paths in the pipeline
    # wrapper can call us before any spawn touched disk).
    if not attempts_dir.exists():
        return None
    budget = PARTIAL_BUDGETS.get(kind, PARTIAL_BUDGET)
    bodies: list[str] = []
    for name in sources:
        src = attempts_dir / name
        if not src.exists():
            continue
        try:
            text = src.read_text(encoding="utf-8")
        except OSError:
            continue
        if not text.strip():
            continue
        if len(text) > budget:
            text = (text[:budget]
                    + f"\n\n... (truncated; full file was {len(text)} chars)")
        bodies.append(f"### {name}\n\n```\n{text}\n```")
    if not bodies:
        return None
    out = drafts_path(problem_dir, kind, goal_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(bodies) + "\n", encoding="utf-8")
    return out


def clear_partial(*, problem_dir: Path, kind: str, goal_id: int) -> None:
    """Remove the per-goal drafts file. Called on pipeline success so
    the next dispatch sees a clean slate. Best-effort; missing file is
    expected (most pipelines never produce a draft)."""
    try:
        drafts_path(problem_dir, kind, goal_id).unlink()
    except FileNotFoundError:
        pass


def read_partial(*, problem_dir: Path, kind: str, goal_id: int) -> str | None:
    """Return the persisted partial content for inclusion in Context.md,
    or None when no draft exists."""
    p = drafts_path(problem_dir, kind, goal_id)
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None
