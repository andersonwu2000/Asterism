"""Per-pipeline progress-note persistence.

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

Why not "save PROPOSAL incrementally" (the original design):
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
inside `problem_dir`, so it's covered by the existing per-problem
sandbox + mathlib allowlist — no separate add-dir needed.
"""
from __future__ import annotations

import sqlite3
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
# Raised 2000→3000 (2026-06-05): a detailed real blocker note (RCF
# s11596, 2290 chars) was tail-truncated, dropping its "Alternative
# direction" conclusion — the highest-value carry-over. 3000 covers
# observed notes whole. NOTE: this is still TAIL truncation; if notes
# >3000 recur and lose their conclusion, switch to head+tail (keep both
# ends, elide the middle) rather than raising the cap further.
PARTIAL_BUDGETS: dict[str, int] = {
    "backward": 3000,
    "builder":  3000,
}
# Back-compat for callers that don't pass `kind`.
PARTIAL_BUDGET = 3000


def drafts_path(problem_dir: Path, kind: str, goal_id: int) -> Path:
    return problem_dir / ".drafts" / f"{kind}_g{goal_id}.md"


def persist_partials(*, attempts_dir: Path, problem_dir: Path,
                     kind: str, goal_id: int,
                     conn: sqlite3.Connection | None = None) -> Path | None:
    """Capture kind's partial outputs from `attempts_dir` into the
    per-goal drafts file. Idempotent — overwrites any prior draft so the
    most recent attempt's draft is what next spawn sees. Returns the
    drafts path on write, None when nothing was captured (no source
    files, all empty, or unknown kind).
    """
    sources = PARTIAL_PERSIST.get(kind)
    if not sources:
        return None
    # Nit-fix: tolerate missing attempts_dir (early
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
    # Live KB antipattern capture from the just-written postmortem note
    # (Phase 12), using the caller's connection — only the production pipeline
    # passes `conn`, so tests that call persist_partials don't touch the KB.
    # Best-effort; a KB hiccup must never affect draft persistence.
    if conn is not None:
        try:
            from ..state import kb_ingest
            if kb_ingest.capture_drafts(conn, path=out, gid=goal_id):
                conn.commit()
        except Exception:  # noqa: BLE001
            pass
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


# ---------------------------------------------------------------------
# patch.lean salvage — orphan-attempts startup recovery
# ---------------------------------------------------------------------
# When daemon is hard-killed (user Stop-Process) the workers' patch.lean
# is orphaned. The postmortem path only fires on watchdog-detected
# timeout (via SIGKILL hook) and even then only captures `_progress.md`.
# This module's salvage hooks below scan orphan attempts dirs at
# startup, extract the theorem name from each patch.lean, map to the
# DB goal, and persist the patch text under a separate drafts slot
# so the next worker on that goal sees it.

import re as _re
import sqlite3 as _sqlite3

_PATCH_FILENAME = "patch.lean"
_PATCH_DRAFTS_BUDGET = 6000  # patch bodies can run longer than progress notes
_PATCH_DRAFT_KIND_SUFFIX = "patch"

# Extract theorem/lemma/def head name. Mirrors dedupe._THM_NAME_RE.
_PATCH_THM_NAME_RE = _re.compile(r"\b(?:theorem|lemma|def)\s+(\S+)")

# Anti-noise: bodies containing only `:= by sorry` (or empty proof)
# carry no useful signal; skip.
_SORRY_ONLY_RE = _re.compile(r":=\s*by\s+sorry\s*$", _re.MULTILINE)


# ── Strategist plan note (2026-07-05) ────────────────────────────────
# The Strategist's PRIVATE cross-wake memory — the third channel next to
# the two worker-facing ones (standing `EmitDirective` broadcast, one-shot
# Inject `brief`). Its curated world-model (plan, progress ledger,
# composition recipes) previously had no home and leaked into the
# directive, taxing every worker spawn (sphere_homology: 9.8KB directive,
# 20 rewrites, monotone growth). Same agent-writes-sandbox /
# framework-persists split as the postmortem progress notes above:
# the agent Writes `_plan.md` in attempts_dir; the framework moves it to
# `.drafts/strategist_plan.md`; the next wake's context inlines it —
# for the Strategist ONLY, never for workers.

PLAN_NOTE_FILENAME = "_plan.md"
# Soft cap (chars): above this the context section carries ONE warning
# line — nothing harder (user call 2026-07-05: the prompt asks for the
# rewrite-don't-hoard spirit; over-constraining beats the purpose).
PLAN_NOTE_SOFT_CAP = 5_000


def plan_note_path(problem_dir: Path) -> Path:
    return problem_dir / ".drafts" / "strategist_plan.md"


def persist_plan_note(*, problem_dir: Path, attempts_dir: Path) -> int | None:
    """Move a freshly-written `_plan.md` from the spawn sandbox into the
    cross-wake drafts slot (full overwrite — the note is a REWRITE by
    contract). Absent file = no update, the prior note stands. Returns
    the persisted size for the telemetry line, None when nothing was
    written. Best-effort: an IO error just keeps the prior note."""
    src = attempts_dir / PLAN_NOTE_FILENAME
    if not src.exists():
        return None
    try:
        text = src.read_text(encoding="utf-8")
        dst = plan_note_path(problem_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")
    except OSError:
        return None
    return len(text)


def read_plan_note(problem_dir: Path) -> str | None:
    p = plan_note_path(problem_dir)
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def patch_drafts_path(problem_dir: Path, kind: str, goal_id: int) -> Path:
    """Drafts slot for salvaged patch.lean — distinct from progress
    note slot (`drafts_path`) so the two surfaces don't clobber each
    other and surface independently in Context.md."""
    return (problem_dir / ".drafts"
            / f"{kind}_g{goal_id}_{_PATCH_DRAFT_KIND_SUFFIX}.lean")


def read_partial_patch(*, problem_dir: Path,
                       kind: str, goal_id: int) -> str | None:
    """Companion to `read_partial` for the patch.lean drafts slot."""
    p = patch_drafts_path(problem_dir, kind, goal_id)
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def clear_partial_patch(*, problem_dir: Path,
                        kind: str, goal_id: int) -> None:
    """Drop the salvaged patch on pipeline success."""
    try:
        patch_drafts_path(problem_dir, kind, goal_id).unlink()
    except FileNotFoundError:
        pass


def _patch_is_substantive(text: str) -> bool:
    """True iff the patch carries a proof body beyond the original
    sorry stub. Empty bodies and `:= by sorry`-only files are skipped
    — surfacing them as a "previous attempt" would mislead."""
    if not text or not text.strip():
        return False
    # If the file contains a `:= by sorry` line, treat it as the stub
    # unless there are also non-sorry lines doing real work. The most
    # common shape is import + theorem header + `:= by sorry`; reject.
    if _SORRY_ONLY_RE.search(text):
        # Count any other tactic-shaped line. Crude heuristic.
        non_trivial = sum(
            1 for ln in text.splitlines()
            if ln.strip()
            and not ln.strip().startswith(("import", "namespace",
                                           "end", "--", "/-", "*/"))
            and ":= by sorry" not in ln
            and ":" in ln or "exact" in ln or "apply" in ln
        )
        if non_trivial < 2:
            return False
    return True


def _resolve_goal_for_slug(conn: "_sqlite3.Connection",
                           slug: str) -> tuple[int, str, str] | None:
    """Look up the goal id + problem + kind hint for a slug. patch.lean
    is Builder-emitted so kind defaults to 'builder'; the kind is used
    as the drafts slot key.

    Returns (goal_id, problem, kind) or None when slug doesn't match
    any goal (could mean the goal was deleted by reset / prune / the
    slug was framework-generated under a different name).
    """
    row = conn.execute(
        "SELECT id, problem, entry_kind FROM goals WHERE slug = ?",
        (slug,),
    ).fetchone()
    if row is None:
        return None
    return (int(row["id"]), str(row["problem"]), "builder")


def salvage_orphan_patches(conn: "_sqlite3.Connection",
                           workspace: Path) -> int:
    """Scan `.attempts/<uuid>/patch.lean` files and persist any
    substantive proof bodies as per-goal drafts. Called at startup
    BEFORE the recovery sweep deletes the orphan dirs.

    Returns the count of patches salvaged. Best-effort: any per-dir
    failure (missing file, unparseable theorem name, slug not in DB,
    DB problem dir not resolvable) is logged and skipped — the
    surrounding cleanup still removes the orphan dir.
    """
    attempts_root = workspace / ".attempts"
    if not attempts_root.exists():
        return 0
    salvaged = 0
    for d in attempts_root.iterdir():
        if not d.is_dir():
            continue
        patch_path = d / _PATCH_FILENAME
        if not patch_path.exists():
            continue
        try:
            text = patch_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not _patch_is_substantive(text):
            continue
        m = _PATCH_THM_NAME_RE.search(text)
        if m is None:
            continue
        slug = m.group(1).strip()
        resolved = _resolve_goal_for_slug(conn, slug)
        if resolved is None:
            print(f"[patch-salvage] orphan {d.name}: slug {slug!r} "
                  f"not in DB; skip", flush=True)
            continue
        goal_id, problem, kind = resolved
        try:
            from ..state import db as _db
            problem_dir = _db.problem_dir(workspace, problem)
        except Exception:
            continue
        out = patch_drafts_path(problem_dir, kind, goal_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        budget_text = text if len(text) <= _PATCH_DRAFTS_BUDGET else (
            text[:_PATCH_DRAFTS_BUDGET]
            + f"\n\n-- (truncated; full patch was {len(text)} chars)"
        )
        try:
            out.write_text(budget_text, encoding="utf-8")
            salvaged += 1
            print(f"[patch-salvage] orphan {d.name} → "
                  f"{out.relative_to(workspace).as_posix()} "
                  f"(slug={slug}, g{goal_id})", flush=True)
        except OSError as e:
            print(f"[patch-salvage] write failed for g{goal_id}: {e}",
                  flush=True)
    return salvaged
