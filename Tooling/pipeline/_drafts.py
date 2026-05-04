"""Per-pipeline partial-output persistence (F55).

When a kind-K worker spawn ends in failure (rc != 0, including timeout),
its in-flight outputs in `attempts_dir` are about to be discarded with
the rest of the ephemeral attempts dir. Persist them under
`problem_dir/.drafts/<kind>_g<gid>.md` so the NEXT spawn's Context.md
can surface them as "your previous incomplete output". Cleared on
successful pipeline (commit / proved) so the next-time-this-goal-opens
path doesn't see stale carry-over.

Motivation: SG (sylvester_gallai) Backward root spawn timed out 3× at
600s and 2× at 720s without producing PROPOSAL.md, because Sonnet
needed > 12 min to compose a Kelly-minimiser decomposition end-to-end.
Each retry was a fresh from-scratch spawn (timeout path clears the F53
warm session_id on purpose, since claude's session may have been killed
mid-write). With this module, a partial PROPOSAL written before the
kill survives across attempts; the next spawn picks up at ~60% rather
than 0%.

attempts_dir is per-spawn (random uuid path); `.drafts/` is per-(kind,
goal) so the carry-over is stable across spawns. `.drafts/` lives
inside `problem_dir`, so it's covered by the existing F44 sandbox + M1
allowlist — no separate add-dir needed.
"""
from __future__ import annotations

from pathlib import Path

# kind → filenames in attempts_dir to capture as the partial output.
# Kept as a one-line dict so future agent kinds (Strategist, Forward,
# ...) can opt in by adding an entry. `verify` intentionally absent —
# F41 already handles its own LLM retry via prompt context.
PARTIAL_PERSIST: dict[str, list[str]] = {
    "backward": ["PROPOSAL.md"],
    "builder":  ["patch.lean"],
}

# Per-file char cap when persisting + inlining. Sized so the partial
# section in Context.md stays tight ("agent 看到的資訊要清楚簡潔");
# truncated content is still useful as a starting sketch. Split per-
# kind because Builder proof bodies (long tactic blocks with `have ...
# ; have ... ; ...` chains) commonly run 4-8 KB; Backward PROPOSAL.md
# is prose and tops out around 2-3 KB even when verbose.
PARTIAL_BUDGETS: dict[str, int] = {
    "backward": 4000,
    "builder":  8000,
}
# Back-compat: kept as the default for callers that don't pass `kind`
# (e.g. tests that instantiate the helper directly).
PARTIAL_BUDGET = 4000


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
