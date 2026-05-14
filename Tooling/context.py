"""Context.md compilation — sections + orchestration.

Extracted from `agent.py`: ~75% of agent.py was Context assembly with
no agent-dispatch concerns. This module owns the `_section_*` helpers,
the failure-digest utilities, and `compile_context`. agent.py now
keeps only WorkArea + spawn_llm + sandbox-path utilities.

Each `_section_*` is pure: `(...) -> list[str]` of lines (with trailing
empty string for blank-line separator). Empty list means "section
absent". `compile_context` orchestrates ordering + writes Context.md.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import context_files, db, lemma_lookup, manifest
from .pipeline import events


# ---------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------

def _section_header(goal: sqlite3.Row) -> list[str]:
    return [
        f"# Context for goal {goal['slug']}",
        "",
        "## Goal statement",
        goal["statement"],
        "",
    ]


def _section_sandbox(strategy_id: int | None = None,
                     goal: sqlite3.Row | None = None) -> list[str]:
    """Universal sandbox info — read-allowlist boundaries + framework
    file conventions. Always rendered (Builder + Backward both need
    to know which paths are accessible). Strategy-specific naming is
    in `_section_strategy_naming` below; that one is Backward-only
    because Builder doesn't fan out into sub-goals.

    Parameters are kept for legacy compatibility but unused — the
    section content is purely static. `brief.py` calls this with
    no args to assemble the cross-spawn BRIEF.md.
    """
    del strategy_id, goal  # static section, params retained for API stability
    return [
        "## Sandbox",
        "- Reads allowed without permission prompts:",
        "  - This goal's problem dir (your cwd).",
        "  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on "
        "Mathlib source.",
        "- Reads NOT allowed: other `Problems/<...>/` dirs — irrelevant "
        "to this goal. Use Loogle / Grep on Mathlib instead.",
        "- `Context.md` + `PAST_*.md` companion files: read-only.",
        "- `patch.lean` is your single output. Lead with `--` annotation "
        "comments, then edit the body (Builder fills in the proof; "
        "Backward edits the strategy skeleton's body — signature locked). "
        "See the kind-specific prompt for layout.",
        "",
    ]


def _section_strategy_naming(strategy_id: int | None,
                             goal: sqlite3.Row) -> list[str]:
    """Backward-only: strategy id token + sub-goal slug rules. Empty
    for Builder (no fan-out into sub-goals)."""
    if strategy_id is None:
        return []
    sid_token = f"s{strategy_id}"
    return [
        "## Strategy naming",
        f"- Strategy id `{sid_token}` (stable across same-session retries). "
        f"Framework owns `_strategy_{sid_token}.lean` and theorem name "
        f"`{sid_token}` — do not change.",
        "- Sub-goal files: `new_<slug>.lean` × N. Pick descriptive "
        "`<slug>` per sub-goal (e.g. `cross_sq_add_inner_sq`). Charset "
        "`[a-z][a-z0-9_]*`, length ≤ 60. Framework auto-suffixes on "
        "collision — uniqueness is not your concern.",
        "- Theorem name inside each sub-goal file MUST equal the slug.",
        "",
    ]


def _section_parent_strategy(conn: sqlite3.Connection,
                             goal: sqlite3.Row) -> list[str]:
    if goal["origin"] != "backward":
        return []
    row = conn.execute(
        "SELECT g.slug AS parent_slug, g.statement AS parent_statement,"
        "       s.proposal_md AS proposal_md "
        "FROM strategy_subgoals ss "
        "JOIN strategies s ON s.id = ss.strategy_id "
        "JOIN goals g ON g.id = s.goal_id "
        "WHERE ss.subgoal_id = ? "
        "ORDER BY ss.strategy_id ASC LIMIT 1",
        (goal["id"],),
    ).fetchone()
    if not row:
        return []
    out = [
        "## Parent goal & strategy",
        f"This goal `{goal['slug']}` is a sub-goal of "
        f"`{row['parent_slug']}`:",
        "",
        f"> {row['parent_statement']}",
        "",
    ]
    if row["proposal_md"]:
        out.extend([
            "Strategy that produced this sub-goal "
            "(parent's PROPOSAL.md excerpt):",
            "```",
            row["proposal_md"][:2000],
            "```",
            "",
        ])
    return out


def _section_mathlib_hints_stable(mfst: manifest.Manifest,
                                   workspace: Path) -> list[str]:
    """Cross-spawn-stable Mathlib lemma surface for BRIEF.md.

    Renders Manifest `mathlib_hints` with their `lake env lean #check`
    resolved signatures. Stable across spawns: only re-rendered when
    BRIEF re-renders (cli init / daemon startup). Per-spawn lemma
    names extracted from this goal's lake errors live in
    `_section_mathlib_lemmas_from_deads` instead.
    """
    names = _hint_names(mfst)
    resolved: dict[str, str] = {}
    if names:
        try:
            infos = lemma_lookup.lookup_batch(names, workspace)
            resolved = {
                info.name: info.signature
                for info in infos.values() if info.found
            }
        except Exception as exc:  # never block render
            print(f"[lemma_lookup] failed, skipping: {exc}", flush=True)

    if not mfst.mathlib_hints:
        return []

    out = [
        "## Mathlib lemmas",
        "Manifest-curated lemma references. Where a signature is "
        "shown, that's the ground truth from `lake env lean #check` — "
        "use it for arg order / instance shape. For raw-text entries, "
        "the hint is the Manifest author's own note.",
        "",
    ]
    rendered: set[str] = set()
    for hint in mfst.mathlib_hints:
        m = re.match(r"\s*([A-Z][\w']*(?:\.[\w']+)+)", hint)
        if m and m.group(1) in resolved:
            nm = m.group(1)
            commentary = hint[m.end():].strip().lstrip("-—").strip()
            if commentary:
                out.append(f"- **{nm}** : `{resolved[nm]}`  ({commentary})")
            else:
                out.append(f"- **{nm}** : `{resolved[nm]}`")
            rendered.add(nm)
        else:
            out.append(f"- {hint}")
    out.append("")
    return out


def _section_mathlib_lemmas_from_deads(deads: list,
                                       workspace: Path) -> list[str]:
    """Per-spawn surface: lemma names Lean errored on in this goal's
    past failed attempts, resolved to current Mathlib signatures.

    Distinct from the BRIEF half: those names depend on this goal's
    failure history and must be re-resolved per spawn. Not rendered
    when there are no error-derived names (typical first-attempt
    case)."""
    names = _names_from_deads(deads)
    if not names:
        return []
    try:
        infos = lemma_lookup.lookup_batch(names, workspace)
        resolved = {
            info.name: info.signature
            for info in infos.values() if info.found
        }
    except Exception as exc:  # never block context generation
        print(f"[lemma_lookup] failed, skipping: {exc}", flush=True)
        resolved = {}

    if not resolved:
        return []
    out = [
        "## Mathlib lemmas (from past lake errors on this goal)",
        "Names Lean reported in prior failures here, resolved to "
        "their current `lake env lean #check` signature. Use these to "
        "fix arg-order / instance-shape mistakes without another "
        "Loogle round-trip.",
        "",
    ]
    for name, sig in resolved.items():
        out.append(f"- **{name}** : `{sig}`")
    out.append("")
    return out


def _hint_names(mfst: manifest.Manifest) -> list[str]:
    """Resolvable names extracted from `mfst.mathlib_hints` (in order,
    de-duped). Hints that don't open with a Lean qualified name are
    rendered as raw text and skipped here."""
    out: list[str] = []
    seen: set[str] = set()
    for hint in mfst.mathlib_hints:
        m = re.match(r"\s*([A-Z][\w']*(?:\.[\w']+)+)", hint)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            out.append(m.group(1))
    return out


def _names_from_deads(deads: list) -> list[str]:
    """Names extracted from `dead_attempts.failure_detail` lake-error
    output. De-duped, first-seen order."""
    out: list[str] = []
    seen: set[str] = set()
    for d in deads:
        for nm in lemma_lookup.extract_lemma_names(d["failure_detail"] or ""):
            if nm not in seen:
                seen.add(nm)
                out.append(nm)
    return out


def _section_manifest_forbidden(mfst: manifest.Manifest) -> list[str]:
    if not mfst.forbidden_lemmas:
        return []
    return [
        "## FORBIDDEN_LEMMAS (from Manifest.md)",
        "**Do NOT use any of the following in your proof or in any "
        "sub-goal docstring; the integrator will reject the proposal.**",
        *(f"- {f}" for f in mfst.forbidden_lemmas),
        "",
    ]


def _section_manifest_notes(mfst: manifest.Manifest) -> list[str]:
    if not mfst.strategic_notes:
        return []
    return [
        "## Strategic notes (from Manifest.md)",
        mfst.strategic_notes,
        "",
    ]


# ---------------------------------------------------------------------
# Failure digest helpers (used by Context summary + tests)
# ---------------------------------------------------------------------

_LEAN_PATH_DUMP_RE = re.compile(r"LEAN_PATH=|lake/packages/|lake/build/")
_FIRST_ERROR_RE = re.compile(
    r"^.*?\berror\b\s*:?\s*(.*)$", re.IGNORECASE)


def _digest_failure(failure_reason: str, failure_detail: str) -> str:
    """One-line digest of a failed pipeline for the Context.md summary.

    The full content is written to PAST_DIRECT_ATTEMPTS.md by context_files —
    here we extract only what the agent needs at-a-glance: which class
    of failure + the actual error message (skipping LEAN_PATH dumps
    and other lake-trace noise that the older inline-everything format
    caught Sonnet looking at 76% of the time)."""
    if not failure_detail:
        return ""

    if failure_reason != "lake_build_error":
        return failure_detail.strip().splitlines()[0][:160]

    for line in failure_detail.splitlines():
        s = line.strip()
        if not s:
            continue
        if _LEAN_PATH_DUMP_RE.search(s):
            continue
        if s.startswith("✖ ") or s.startswith("error: build failed"):
            continue
        m = _FIRST_ERROR_RE.match(s)
        if m and m.group(1).strip():
            return m.group(1).strip()[:200]
    for line in failure_detail.splitlines():
        s = line.strip()
        if s and not _LEAN_PATH_DUMP_RE.search(s):
            return s[:160]
    return ""


def _ago(ts_iso: str | None) -> str:
    """Render dead_attempt.ts as `Nmin ago` / `Nh ago`."""
    if not ts_iso:
        return ""
    try:
        t = datetime.fromisoformat(ts_iso)
    except (TypeError, ValueError):
        return ""
    now = datetime.now(timezone.utc)
    delta = (now - t).total_seconds()
    if delta < 0:
        return "just now"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}min ago"
    return f"{int(delta // 3600)}h ago"


# ---------------------------------------------------------------------
# History sections (past attempts / verify failures / dead strategies)
# ---------------------------------------------------------------------

def _section_brief_inline(problem_dir: Path) -> list[str]:
    """Inline `Problems/<p>/BRIEF.md` content into Context.md so the
    agent's read surface stays single-file (BRIEF is framework-rendered
    cross-spawn stable context — sandbox / forbidden / mathlib hints /
    library / strategic notes; see `Tooling/brief.py`). Returns [] when
    BRIEF.md is missing (legacy init, mid-reset race) — Context.md
    proceeds without it; safer than crashing dispatch on a missing
    optional file."""
    p = problem_dir / "BRIEF.md"
    if not p.exists():
        return []
    try:
        content = p.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not content:
        return []
    return [content, ""]


def _section_lessons_inline(problem_dir: Path) -> list[str]:
    """Inline `Problems/<p>/LESSONS.md` content. LESSONS is the agent-
    curated cross-spawn experience surface (Edit'd by the reflection
    spawn after successful pipelines); the file may be empty (initial
    state) or missing (legacy)."""
    p = problem_dir / "LESSONS.md"
    if not p.exists():
        return []
    try:
        content = p.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not content:
        return []
    return [
        "## Lessons learned on this problem",
        "_Cross-spawn observations recorded by past agents on this_",
        "_problem. Sentence-per-line. Edit only via the reflection_",
        "_spawn invoked at successful pipeline terminals._",
        "",
        content,
        "",
    ]


def _section_proved_goals(conn: sqlite3.Connection,
                          goal: sqlite3.Row) -> list[str]:
    """Grep entrypoint for proved goals in this problem. Section omitted
    when the count is zero (fresh problem).

    Each proved goal source carries a `-- <slug>: <summary>` leading
    comment block (Builder Phase 6 / Verify propagate). Framework only
    points the agent at the directory; it doesn't push a candidate list.
    Same pattern as Mathlib (grep `.lake/packages/mathlib/`) and Library.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM goals "
        "WHERE problem = ? AND status = 'proved' "
        "  AND id != ? AND alias_target_id IS NULL",
        (goal["problem"], goal["id"]),
    ).fetchone()
    if row is None or int(row["n"]) == 0:
        return []
    n = int(row["n"])
    return [
        "## Proved goals on this problem (grep entrypoint)",
        f"- {n} proved goal{'s' if n != 1 else ''} so far. Sources at "
        f"`Problems/{goal['problem']}/proofs/L_<slug>.lean`, each opening "
        "with a `-- <slug>: <summary>` comment block.",
        "- Grep the directory for slugs / summary text matching the "
        "current goal — e.g. `rg -l 'cross.*inner' Problems/"
        f"{goal['problem']}/proofs/` then Read the hits. Useful for "
        "spotting an already-proved sub-goal to alias against, or a "
        "prior bridge lemma to apply.",
        "",
    ]


def _section_library_available(mfst, workspace) -> list[str]:
    """List Library/<Topic>/INDEX.md entries for the topics inferred
    from `mfst.lemma_hints` (any `Library.<Topic>.*` entries)."""
    from . import library  # local import to avoid cycle at module load
    topics = library.topics_from_hints(mfst.all_hints)
    if not topics:
        return []
    lib_root = workspace / "Library"
    chunks: list[str] = []
    for topic in topics:
        idx_file = lib_root / topic / "INDEX.md"
        if not idx_file.exists():
            continue
        try:
            body = idx_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        entries = [
            ln for ln in body.splitlines()
            if ln.strip().startswith("- `")
        ]
        if entries:
            chunks.append(f"### {topic}")
            chunks.extend(entries)
            chunks.append("")
    if not chunks:
        return []
    return [
        "## Library available (filtered by lemma_hints topics)",
        "",
        "Theorems already proved by Asterism in prior Problems. Import "
        "via `import Library.<Topic>.<problem>` and use the theorem "
        "name `<problem>`. Signatures resolve through the same lemma "
        "lookup as Mathlib hints.",
        "",
        *chunks,
    ]


def _section_goal_history(*,
                          direct_events: list,
                          verify_events: list,
                          dead_strat_events: list,
                          infeasible_sub_events: list,
                          show_verifies: bool) -> list[str]:
    """`## Goal history` umbrella — past failures on this goal in one
    place, partitioned by event_type into sub-sections. Replaces the
    previous separate `## Previous attempts on THIS goal` /
    `## Past decompositions that failed Verify` /
    `## Prior strategies that died` sections.

    Sub-sections render only when their bucket is non-empty AND their
    kind-gate allows. Umbrella header itself is suppressed when every
    sub-section is empty (no header for an empty body).

    Sub-sections (in order):
      ### Direct attempts on this goal              — direct_attempt events
      ### Sibling decompositions that failed Verify — verify_failure (legacy event)
      ### Strategies whose decomposition died        — dead_strategy events
      ### Sub-goals reported infeasible              — infeasible_sub events (NEW)

    Reasons NOT included here (and won't ever be — they're filtered
    out at the `events.py` projection layer): `spawn_fast_fail`
    (infra noise), `agent_infeasible` directly on this goal (the
    sub is shelved; cross-goal projected to parent's infeasible_sub
    above), and the framework / DB / FS race reasons. See
    `docs/failure_modes.md` §3.
    """
    parts: list[list[str]] = []

    # Direct attempts: no kind-gate (was `show_attempts` only) — the
    # goal's failure history is a property of the goal, not of the
    # pipeline kind. Backward retry needs this to see SG-g142-class
    # cases (its own prior `lake_build_error` rows) and the hand-off
    # signal from Builder declines that previously lived in a separate
    # `## Why Builder declined this goal` section.
    if direct_events:
        sub = ["### Direct attempts on this goal", ""]
        # If any attempt is `agent_declined`, surface it up front so the
        # next dispatch (typically Backward, since declined jumps attempts
        # to BUILDER_THRESHOLD) sees decomposition reasoning early. The
        # individual block still renders the full PROPOSAL.md text.
        if any(e.get("failure_reason") == "agent_declined"
               for e in direct_events):
            sub.append(
                "Note: blocks with `agent_declined` are Builder declining "
                "this goal as decomposition-needed (PROPOSAL.md carries "
                "the specific hard parts identified). Design the "
                "decomposition to address them."
            )
            sub.append("")
        for i, d in enumerate(direct_events, 1):
            sub.append(context_files.render_attempt_block(i, d).rstrip())
            sub.append("")
        parts.append(sub)

    if show_verifies and verify_events:
        sub = [
            "### Sibling decompositions that failed Verify",
            "",
            "Earlier Backward attempts decomposed this goal but the "
            "combination patch did not elaborate against the sub-goal "
            "proofs. Avoid re-proposing a decomposition with the same "
            "typing shape.",
            "",
        ]
        for i, r in enumerate(verify_events, 1):
            sub.append(context_files.render_strategy_block(i, r).rstrip())
            sub.append("")
        parts.append(sub)

    if dead_strat_events:
        sub = [
            "### Strategies whose decomposition died",
            "",
            "Earlier Backward attempts produced the decompositions below "
            "— each killed because at least one of its sub-goals could "
            "not be proved (cascade-shelve). Do NOT re-propose a "
            "decomposition that hinges on the same dead sub-goal — pick "
            "a structurally different angle.",
            "",
        ]
        for s in dead_strat_events:
            sub.append(f"#### Dead strategy s{s['id']}")
            sub.append("Sub-goals it produced:")
            for sub_g in s["subs"]:
                mark = (f"({sub_g['status']})"
                        if sub_g["status"] != "shelved" else "(shelved)")
                stmt = sub_g["statement"].strip()
                if len(stmt) > 300:
                    stmt = stmt[:300].rstrip() + " …"
                stmt_oneline = " ".join(stmt.split())
                sub.append(f"- `{sub_g['slug']}` {mark} — {stmt_oneline}")
                if sub_g.get("root_cause"):
                    sub.append(f"  **Root cause**: {sub_g['root_cause']}")
            sub.append("")
        parts.append(sub)

    if show_verifies and infeasible_sub_events:
        sub = [
            "### Sub-goals declined",
            "",
            "Sub-goals from earlier decompositions of THIS goal that the "
            "prover declined via a `decline:` directive. Three failure "
            "reasons surface here:",
            "",
            "- `agent_infeasible` (`unprovable` directive) — sub-goal is "
            "false in scope; do NOT re-propose a decomposition around "
            "the same type.",
            "- `parent_needs_fix` (`return_to_parent` directive) — the "
            "sub-goal can be proved IF this goal's strategy is fixed "
            "as the **Fix hint** below describes. Prefer keeping the "
            "prior strategy shape and applying the fix over switching "
            "to a different decomposition.",
            "- `agent_shelved` (`shelve` directive) — prover stuck "
            "without a counterexample; treat as soft information.",
            "",
        ]
        for e in infeasible_sub_events:
            stmt = (e.get("sub_statement") or "").strip()
            if len(stmt) > 300:
                stmt = stmt[:300].rstrip() + " …"
            stmt_oneline = " ".join(stmt.split())
            reason = e.get("failure_reason") or "agent_infeasible"
            sub.append(
                f"- `{e['sub_slug']}` *(reason: {reason})* — {stmt_oneline}"
            )
            if e.get("root_cause"):
                sub.append(f"  **Root cause / fix hint**: {e['root_cause']}")
        sub.append("")
        parts.append(sub)

    if not parts:
        return []

    # Umbrella header + companion-file pointer.
    out = [
        "## Goal history",
        "",
        "Past failures on this goal — use to avoid re-proposing "
        "approaches that already failed. Full content (deeper context, "
        "raw lake stderr, full PROPOSAL.md / counterexample texts) "
        "in `PAST_DIRECT_ATTEMPTS.md`, `PAST_VERIFY_FAILURES.md`, "
        "`PAST_DEAD_STRATEGIES.md` when present.",
        "",
    ]
    for sub in parts:
        out.extend(sub)
    return out


def _section_prior_partial(kind: str | None, problem_dir: Path,
                           goal_id: int) -> list[str]:
    """Surface the postmortem progress note (if any) from a prior
    timed-out spawn on THIS (goal, kind) pair. The note is the
    short state + blocker dump the framework collected via a
    `--resume`-based postmortem call right after the main spawn was
    SIGKILL'd; it's a starting sketch, not a partial deliverable.

    Stays concise: header + 1-line orientation + the note (already
    bounded by the postmortem prompt's ~150-word target plus a hard
    PARTIAL_BUDGETS cap)."""
    if kind not in ("backward", "builder"):
        return []
    try:
        from .pipeline import _drafts
    except ImportError:
        return []
    body = _drafts.read_partial(problem_dir=problem_dir, kind=kind,
                                goal_id=goal_id)
    if not body:
        return []
    return [
        "## Your previous progress note",
        "",
        "Your previous spawn on this goal timed out. The framework "
        "ran a short postmortem to capture where you got and what "
        "blocked you. Pick up from this sketch.",
        "",
        body.rstrip(),
        "",
    ]


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------

def compile_context(conn: sqlite3.Connection, *, goal: sqlite3.Row,
                    mfst: manifest.Manifest, attempts_dir: Path,
                    strategy_id: int | None = None,
                    kind: str | None = None) -> Path:
    """Write Context.md into attempts_dir. Pulls from DB + Manifest.

    `strategy_id`: when set (Backward worker), write a 'Strategy
    naming' section pinning sub-goal slug prefixes to `s<sid>_`.

    `kind`: 'builder' | 'backward' | None — gates which Goal history
    sub-sections render. Most of the kind-asymmetric gating was
    collapsed; current state:
      - `### Direct attempts on this goal` — kind-agnostic, always
        rendered (was builder-only; SG g142 needed it for Backward).
        Builder declines now appear here as `agent_declined` rows
        (was a separate `## Why Builder declined` section).
      - `### Strategies whose decomposition died` — kind-agnostic.
      - `### Sibling decompositions that failed Verify` — kind ∈
        {backward, None}; Builder retry has no actionable read.
      - `### Sub-goals reported infeasible` — kind ∈ {backward, None};
        same reasoning.

    Also surfaces the persisted partial output (PROPOSAL.md for
    backward, patch.lean for builder) from a prior failed/timed-out
    spawn, so the agent picks up where it left off instead of starting
    fresh.

    Section ordering — keep stable; agents may have learned to scan
    top-down. Each section function returns `[]` when not applicable
    so the resulting Context.md only contains sections with content.
    """
    workspace = attempts_dir.parent.parent  # .attempts/<pid> → workspace
    problem_dir = db.problem_dir(workspace, goal["problem"])

    # Project DB rows into Event objects via events.py.
    # `_NON_AGENT_REASONS` filter lives in events.py; dedupe between
    # verify_failure and dead_strategy is here because Builder kind
    # must skip verify_failure but still see dead_strategy intact —
    # events.py can't know whether verify_failure is rendered.
    direct_events = events.direct_attempts(conn, int(goal["id"]), k=5)
    verify_events = events.verify_failures(conn, int(goal["id"]), k=5)
    infeasible_sub_events = events.infeasible_subs(
        conn, int(goal["id"]), k=5)

    # `show_attempts` retired: `### Direct attempts on this goal` is
    # now kind-agnostic (a goal's failure history is its own property).
    # `show_verifies` still gates the verify_failure / infeasible_sub
    # sub-sections — those are decomposition-shape signals that have
    # no actionable read for Builder.
    show_verifies = kind in (None, "backward")

    # Dedupe dead_strategy against verify_failure only when both render
    # for this audience. Builder kind suppresses verify_failure → no
    # exclude set → all dead strategies surface.
    exclude_ids = (
        {int(e["target_id"]) for e in verify_events}
        if show_verifies else set()
    )
    dead_strat_events = events.dead_strategies(
        conn, int(goal["id"]), k=5, exclude_strategy_ids=exclude_ids,
    )

    # Section ordering — cross-spawn-stable content (BRIEF + LESSONS)
    # leads so prompt-cache prefix-matching gets maximal hit:
    # within one Manifest version + LESSONS state, the entire
    # `BRIEF.md` + `LESSONS.md` block is byte-identical across all
    # spawns of this problem. Putting them first means cache-able
    # prefix length is the BRIEF + LESSONS size (~2-10 KB) rather
    # than zero. Per-goal / per-spawn surfaces follow.
    sections: list[list[str]] = [
        _section_brief_inline(problem_dir),
        _section_lessons_inline(problem_dir),
        _section_header(goal),
        _section_strategy_naming(strategy_id, goal),
        _section_parent_strategy(conn, goal),
        _section_mathlib_lemmas_from_deads(direct_events, workspace),
        _section_proved_goals(conn, goal),
        _section_prior_partial(kind, problem_dir, int(goal["id"])),
        _section_goal_history(
            direct_events=direct_events,
            verify_events=verify_events,
            dead_strat_events=dead_strat_events,
            infeasible_sub_events=infeasible_sub_events,
            show_verifies=show_verifies,
        ),
    ]

    parts: list[str] = []
    for section in sections:
        parts.extend(section)

    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")

    # Write companion reference files for the bulky / lazy-load
    # content (Context.md only carries digests + pointers). The
    # progress note from a prior timed-out spawn is rendered ONLY in
    # Context.md (must-see channel), not duplicated into the companion
    # — agents miss companion files, so the inline section is the
    # canonical surface.
    context_files.write_past_attempts(direct_events, attempts_dir)
    context_files.write_past_backward(verify_events, attempts_dir)
    context_files.write_past_dead_strategies(dead_strat_events,
                                             attempts_dir)

    return out
