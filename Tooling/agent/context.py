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

from . import context_files
from ..state import db, manifest
from ..knowledge import lemma_lookup
from ..pipeline import events


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
    and other lake-trace noise that, under the older inline-everything
    format, made up 76% of what Sonnet ended up reading)."""
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


def _kb_entry_lines(r: sqlite3.Row) -> list[str]:
    """One KB entry as a bullet (title) plus any body lines indented beneath."""
    lines = [f"- {(r['title'] or '').strip()}"]
    body = (r["body"] or "").strip()
    if body:
        lines += [f"  {bl}" for bl in body.splitlines()]
    return lines


def _section_lessons_inline(conn: sqlite3.Connection, problem: str,
                            goal_id: int | None = None) -> list[str]:
    """Inline this problem's KB knowledge: lessons (confirmed cross-spawn
    experience, problem-wide) and antipatterns (approaches that hit a wall).
    Sourced from the `kb_entries` store (Phase 12). `goal_id` filters
    node-scoped antipatterns to this goal — a goal sees the walls hit on
    ITSELF, not every node's; lessons stay problem-wide."""
    from ..state import kb
    grouped = kb.query(conn, problem=problem, goal_id=goal_id)
    lessons = grouped["lessons"]
    antis = grouped["antipatterns"]
    if not lessons and not antis:
        return []
    out: list[str] = []
    if lessons:
        out += [
            "## Lessons learned on this problem",
            "_Cross-spawn observations recorded by past agents on this_",
            "_problem. Maintained by the reflection spawn._",
            "",
        ]
        for r in lessons:
            out += _kb_entry_lines(r)
        out.append("")
    if antis:
        out += [
            "## Antipatterns on this problem",
            "_Approaches that already hit a wall here — don't repeat them._",
            "",
        ]
        for r in antis:
            out += _kb_entry_lines(r)
        out.append("")
    return out


_PROVED_GOAL_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]+")
# Tokens that appear in virtually every Lean theorem and add no
# discriminative signal. Conservative drop set — keep mathlib-namespace
# words like Module/LinearMap/Matrix because they ARE informative for
# domain-specific matching.
_PROVED_GOAL_NOISE_TOKENS = frozenset({
    "type", "prop", "sort", "forall", "fun", "have", "show", "sorry",
    "true", "false", "self", "this", "iff", "imp", "exact", "intro",
    "apply", "rfl", "simp", "rcases", "obtain", "refine", "use",
    "let", "match", "fix", "with", "where", "from", "then", "else",
    "and", "the", "for", "all", "any",
})


def _section_proved_goals_tokens(text: str) -> set[str]:
    """Identifier-shaped tokens from a Lean statement, used for keyword
    overlap scoring against the current goal's parent statement.

    Lowercased + min length 4 to drop short noise (`x`, `y`, `n`, `Fin`).
    `_PROVED_GOAL_NOISE_TOKENS` removes universally-frequent words.
    """
    tokens: set[str] = set()
    for tok in _PROVED_GOAL_TOKEN_RE.findall(text or ""):
        if len(tok) < 4 or tok.isdigit():
            continue
        low = tok.lower()
        if low in _PROVED_GOAL_NOISE_TOKENS:
            continue
        tokens.add(low)
    return tokens


def _section_proved_goals(conn: sqlite3.Connection,
                          goal: sqlite3.Row,
                          workspace: Path) -> list[str]:
    """Top-K curated proved siblings + grep entrypoint footer.

    Pre-2026-05-26: pure grep entrypoint ("N goals — go search proofs/")
    on the principle that framework shouldn't push a candidate list
    (avoid noise from 100+ proved goals). Jordan 2026-05-25→26 disaster
    exposed the gap: Backward agent didn't actually grep, defensively
    decomposed into `_alias` / `_2` variants of already-proved siblings
    (9 confirmed cases). Cite step in backward.md was advisory only —
    agents skipped it without enforcement.

    Pragmatic upgrade: framework runs cheap keyword extraction on the
    parent statement, intersects with each proved sibling's statement
    tokens, surfaces the top 3 by overlap as a curated list. Agents
    still self-help via grep for broader search — the footer points to
    that. Top 3 is the cognitive sweet spot (1 → spotty, 5+ → noisy
    enough that agent skims past).

    Lower bound: at least 1 overlap-token. If parent statement is so
    generic nothing scores, fall back to the grep-only entrypoint.
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

    parent_tokens = _section_proved_goals_tokens(goal["statement"] or "")
    scored: list[tuple[int, sqlite3.Row]] = []
    if parent_tokens:
        for r in conn.execute(
            "SELECT id, slug, statement, lean_path FROM goals "
            "WHERE problem = ? AND status = 'proved' "
            "  AND id != ? AND alias_target_id IS NULL",
            (goal["problem"], goal["id"]),
        ):
            cand_tokens = _section_proved_goals_tokens(r["statement"] or "")
            score = len(parent_tokens & cand_tokens)
            if score >= 1:
                scored.append((score, r))
        scored.sort(key=lambda sr: (-sr[0], sr[1]["id"]))
    top = scored[:3]

    lines = [f"## Proved siblings on this problem ({n} total)"]
    if top:
        lines.append(
            "Top 3 by keyword overlap with your parent statement (framework-"
            "computed via token intersection). **Consider citing one inline** "
            "(`exact <slug> args` or `apply @Problems.<problem>.<slug> "
            "<;> assumption`) before registering a sub-goal that may "
            "duplicate. Tier 1 dedupe at submit catches `_alias`/`_N` "
            "suffix variants regardless; this section surfaces alpha-"
            "equivalent siblings whose names diverge.")
        lines.append("")
        # Show each sibling's FULL signature (binders + conclusion) so the
        # agent can judge citability inline. The old 140-char statement
        # preview cut off mid-binders — the single most-reported reuse
        # friction (agent_feedback C2, ~35) — forcing a Read of the proof
        # file. Source the signature from the proof file (ground truth,
        # incl. explicit args the DB statement may omit); fall back to the
        # DB statement if the file/header can't be read.
        from ..pipeline import _signature_prefix
        for score, r in top:
            sig = ""
            try:
                txt = (workspace / r["lean_path"]).read_text(encoding="utf-8")
                sig = _signature_prefix(txt, r["slug"]).strip()
            except OSError:
                sig = ""
            shown = " ".join((sig or (r["statement"] or "")).split())
            lines.append(f"- `{r['slug']}` (overlap={score}): `{shown}`")
        lines.append("")
    lines.append(
        f"For broader search beyond the curated 3, grep "
        f"`Problems/{goal['problem']}/proofs/L_<slug>.lean` for the "
        "current goal's keywords. Every file carries the proved "
        "`theorem`/`def <slug>` line (always greppable); most also open "
        "with a leading `--` summary — Builder proofs lead with "
        "`-- <slug>: <summary>`, decomposition proofs with a `--` "
        "rationale block.")
    lines.append("")
    return lines


def _section_library_available(mfst, workspace) -> list[str]:
    """Surface the reusable Library — theorems Asterism already proved and
    harvested from prior Problems — to the PROVING agent, so it can cite
    them instead of re-deriving (Library-as-input).

    Reads the single `Library/INDEX.md` (the Librarian `finish` marker),
    parses its `## <problem>` sections, and renders a COMPACT menu of the
    Library modules in this problem's own domain (e.g. a `LinearAlgebra.*`
    problem sees the `LinearAlgebra.*` Library), plus any `Library.*`
    entries named in the Manifest's `lemma_hints` (highlighted as suggested
    citations, cross-domain allowed). The agent has read access to
    `Library/` — it greps there for exact signatures; the menu just tells
    it what exists and how to cite. Returns [] when the Library has nothing
    relevant (keeps unrelated problems' Context clean)."""
    import re as _re
    index = workspace / "Library" / "INDEX.md"
    if not index.exists():
        return []
    try:
        text = index.read_text(encoding="utf-8")
    except OSError:
        return []
    sections: list[tuple[str, list[str]]] = []
    cur: str | None = None
    decls: list[str] = []
    for ln in text.splitlines():
        m = _re.match(r"^##\s+(.+?)\s*$", ln)
        if m:
            if cur is not None:
                sections.append((cur, decls))
            cur, decls = m.group(1), []
            continue
        m = _re.match(r"^-\s+`([\w.]+)`", ln)
        if m and cur is not None:
            decls.append(m.group(1))
    if cur is not None:
        sections.append((cur, decls))
    if not sections:
        return []

    problem = mfst.problem or ""
    domain = problem.split(".")[0] if "." in problem else problem
    relevant = [(p, d) for p, d in sections
                if d and (p.split(".")[0] == domain)]
    hinted = [h for h in mfst.all_hints if h.startswith("Library.")]
    if not relevant and not hinted:
        return []

    out = [
        "## Library available (reusable — proved in prior Problems)",
        "",
        "Theorems Asterism already proved and harvested into `Library/`. "
        "**Prefer citing these over re-deriving.** To use one: "
        "`import <module>` (the dotted prefix before the decl's last "
        "component) and reference it by its full name. You have read "
        "access to `Library/` — grep there for exact signatures. The R1 "
        "search-before-reconstruct rule covers Library too.",
        "",
    ]
    if hinted:
        out.append("Suggested citations (this problem's `lemma_hints`):")
        out += [f"- `{h}`" for h in hinted]
        out.append("")
    if relevant:
        out.append(f"Library modules in the `{domain}` domain "
                   "(grep `Library/` for signatures):")
        for p, d in relevant:
            keystone = next((x for x in d if x.endswith(".main")), None)
            tag = f" — keystone `{keystone}`" if keystone else ""
            out.append(f"- **{p}** ({len(d)} decls){tag}")
        out.append("")
    return out


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
            "not be proved (cascade-shelve).",
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
        from ..pipeline import _drafts
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


def _section_prior_patch(kind: str | None, problem_dir: Path,
                         goal_id: int) -> list[str]:
    """Surface the patch.lean salvaged from a prior orphaned spawn —
    the daemon's startup recovery captures any substantive patch.lean
    body left in an orphan `.attempts/<uuid>/` dir (Builder writes
    patch.lean during proof attempts; user `Stop-Process` on daemon
    or OS crash leaves it behind without ever promoting to the
    workspace file).

    Unlike `_section_prior_partial`'s narrative note, this surfaces
    the actual proof code the previous spawn was working on. The
    next Builder reads it as an unverified starting point — may copy
    intact, refactor, or discard.
    """
    if kind != "builder":
        return []
    try:
        from ..pipeline import _drafts
    except ImportError:
        return []
    body = _drafts.read_partial_patch(
        problem_dir=problem_dir, kind=kind, goal_id=goal_id)
    if not body:
        return []
    return [
        "## Your previous patch.lean attempt (unverified)",
        "",
        "A prior spawn on this goal was interrupted before its "
        "patch.lean could be promoted to the workspace. The body "
        "below is what that spawn last wrote. It may be a complete "
        "proof, a partial sketch, or a wrong direction — treat as a "
        "starting point, validate via the LSP before relying on it.",
        "",
        "```lean",
        body.rstrip(),
        "```",
        "",
    ]


# ---------------------------------------------------------------------
# Phase 2 — Strategist directive / brief sections
# ---------------------------------------------------------------------

def _section_strategist_directive(conn: sqlite3.Connection,
                                  problem: str) -> list[str]:
    """Render `problems.strategist_directive` as a top-level Context.md
    section if non-empty. Standing directive — applies to every pipeline
    cold-start (Backward / Builder / Forward) until Strategist overwrites
    with another EmitDirective / Reopen-with-directive commit.

    Empty / NULL directive → returns []. No-op if the `problems` row's
    Phase 2 columns are absent (pre-migration DB).
    """
    try:
        row = conn.execute(
            "SELECT strategist_directive FROM problems WHERE name = ?",
            (problem,),
        ).fetchone()
    except sqlite3.OperationalError:
        # Pre-Phase 2 schema (column missing).
        return []
    if row is None:
        return []
    directive = row["strategist_directive"]
    if directive is None or not str(directive).strip():
        return []
    return [
        "## Strategist directive",
        "",
        str(directive).strip(),
        "",
    ]


def _section_strategist_brief(conn: sqlite3.Connection,
                              decision_id: int | None) -> list[str]:
    """Render `strategist_decisions.brief` as a top-level Context.md
    section if `decision_id` is set and the row has non-empty brief.
    Per-pipeline one-shot — this only renders for pipelines spawned
    by a Strategist Inject decision (queue.decision_id FK).

    decision_id=None (BFS-auto-dispatched pipeline) → returns []. No-op
    if strategist_decisions table is absent.
    """
    if decision_id is None:
        return []
    try:
        row = conn.execute(
            "SELECT brief FROM strategist_decisions WHERE id = ?",
            (int(decision_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        return []
    if row is None:
        return []
    brief = row["brief"]
    if brief is None or not str(brief).strip():
        return []
    return [
        "## Strategist brief",
        "",
        str(brief).strip(),
        "",
    ]


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------

def compile_context(conn: sqlite3.Connection, *, goal: sqlite3.Row,
                    mfst: manifest.Manifest, attempts_dir: Path,
                    strategy_id: int | None = None,
                    kind: str | None = None,
                    decision_id: int | None = None) -> Path:
    """Write Context.md into attempts_dir. Pulls from DB + Manifest.

    `strategy_id`: when set (Backward worker), write a 'Strategy
    naming' section pinning sub-goal slug prefixes to `s<sid>_`.

    `decision_id`: Phase 2 — when set, the spawning queue row was
    emitted by a Strategist Inject decision; pulls
    `strategist_decisions.brief` into a `## Strategist brief` section.
    None means BFS-auto-dispatched (no brief, only directive).

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
        _section_lessons_inline(conn, str(goal["problem"]), int(goal["id"])),
        # Phase 2 — Strategist injections sit between cross-spawn-stable
        # content (BRIEF / LESSONS) and per-goal sections. Directive is
        # problem-level standing (every cold-start); brief is per-decision
        # one-shot (only when Strategist Inject spawned this pipeline).
        _section_strategist_directive(conn, str(goal["problem"])),
        _section_strategist_brief(conn, decision_id),
        _section_header(goal),
        _section_library_available(mfst, workspace),
        _section_strategy_naming(strategy_id, goal),
        _section_parent_strategy(conn, goal),
        _section_mathlib_lemmas_from_deads(direct_events, workspace),
        _section_proved_goals(conn, goal, workspace),
        _section_prior_partial(kind, problem_dir, int(goal["id"])),
        _section_prior_patch(kind, problem_dir, int(goal["id"])),
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
