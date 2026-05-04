"""Context.md compilation — sections + orchestration.

Extracted from `agent.py` (P2-#2 audit): ~75% of agent.py was Context
assembly with no agent-dispatch concerns. This module owns the
`_section_*` helpers, the failure-digest utilities, and
`compile_context`. agent.py now keeps only WorkArea + spawn_llm +
sandbox-path utilities and re-exports the public names for back-compat.

Each `_section_*` is pure: `(...) -> list[str]` of lines (with trailing
empty string for blank-line separator). Empty list means "section
absent". `compile_context` orchestrates ordering + writes Context.md.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import context_files, db, lemma_lookup, manifest, playbook


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


def _section_sandbox(strategy_id: int | None,
                     goal: sqlite3.Row) -> list[str]:
    """Universal sandbox info — read-allowlist boundaries + framework
    file conventions. Always rendered (Builder + Backward both need
    to know which paths are accessible). Strategy-specific naming is
    in `_section_strategy_naming` below; that one is Backward-only
    because Builder doesn't fan out into sub-goals.

    P0-#4: prior version returned [] when strategy_id is None,
    silently denying Builder kind the read-scope hints — Builder then
    burned turns hitting permission prompts the new F54 allowlist
    introduced.
    """
    return [
        "## Sandbox",
        "- Reads allowed without permission prompts:",
        "  - This goal's problem dir (your cwd).",
        "  - `.lake/packages/mathlib/Mathlib/` for `rg`/`Read` on "
        "Mathlib source.",
        "- Reads NOT allowed: other `Problems/<...>/` dirs — they're "
        "irrelevant to this goal. Use Loogle / Grep on Mathlib instead.",
        "- Files framework wrote (read & edit, do NOT rename):",
        "  - `patch.lean` — proof patch (Builder writes body; Backward "
        "edits the locked-signature skeleton, body only).",
        "  - `Context.md`, `PAST_ATTEMPTS.md`, `PAST_BACKWARD.md` "
        "(when present) — read-only reference.",
        "- Files you write:",
        "  - `PROPOSAL.md` — strategy / approach explanation.",
        "",
    ]


def _section_strategy_naming(strategy_id: int | None,
                             goal: sqlite3.Row) -> list[str]:
    """Backward-only: slug naming pinned to this strategy id. Builder
    doesn't fan out into sub-goals so this section is empty for it."""
    if strategy_id is None:
        return []
    sid_token = f"s{strategy_id}"
    return [
        "## Strategy naming",
        f"- This Backward attempt is strategy `{sid_token}` (stable "
        "across same-session retries).",
        f"- Sub-goal files you write: `new_{sid_token}_sub_<N>.lean` × N. "
        f"Theorem name in each file = `{sid_token}_sub_<N>` (filename "
        f"minus `new_` and `.lean`).",
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


def _section_mathlib_lemmas(mfst: manifest.Manifest,
                             deads: list[sqlite3.Row],
                             workspace: Path) -> list[str]:
    """Merged successor of the previous separate `## Mathlib hints`
    + `## Lemma references`. Manifest hints often point at a name; the
    lookup pass resolves the same name to a real `lake env lean #check`
    signature. Showing them as one block (signature when resolved, raw
    hint text otherwise) saves a heading + a prose preamble and lets
    the agent read each lemma's name + signature in one place."""
    names = _collect_lemma_names(deads, mfst)
    resolved: dict[str, str] = {}
    if names:
        try:
            infos = lemma_lookup.lookup_batch(names, workspace)
            resolved = {
                info.name: info.signature
                for info in infos.values() if info.found
            }
        except Exception as exc:  # never block context generation
            print(f"[lemma_lookup] failed, skipping: {exc}", flush=True)

    if not mfst.mathlib_hints and not resolved:
        return []

    out = [
        "## Mathlib lemmas",
        "Names from Manifest plus those Lean errored on in past "
        "attempts. Where a signature is shown, that's the ground "
        "truth from `lake env lean #check` — use it for arg order / "
        "instance shape. For raw-text entries, the hint is the "
        "Manifest author's own note.",
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
    for name, sig in resolved.items():
        if name in rendered:
            continue
        out.append(f"- **{name}** : `{sig}`")
    out.append("")
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


def _section_playbook(goal: sqlite3.Row, workspace: Path) -> list[str]:
    """F22 — agent-curated success idioms accumulated across prior
    strategies on this problem. Author intent (mathlib_hints /
    strategic_notes) above represent design; this section is what the
    framework has empirically learned works."""
    pb_text = playbook.read_playbook(goal["problem"], workspace)
    if not pb_text.strip():
        return []
    return [
        "## Past wins on this problem (playbook)",
        "Idioms that proved earlier strategies on this same problem. "
        "When the current goal matches a pattern below, prefer the "
        "noted idiom over re-deriving from scratch.",
        "",
        pb_text.rstrip(),
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

    The full content is written to PAST_ATTEMPTS.md by context_files —
    here we extract only what the agent needs at-a-glance: which class
    of failure + the actual error message (skipping LEAN_PATH dumps
    and other lake-trace noise that 76% of pre-F26 dead_attempts
    caught Sonnet looking at)."""
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

def _section_past_attempts(deads: list[sqlite3.Row]) -> list[str]:
    """F43 — full inline rendering of PAST_ATTEMPTS history into
    Context.md. Companion file is still written by
    `context_files.write_past_attempts` for forensics + future
    re-reading; this section duplicates its content so the agent
    can't miss it."""
    if not deads:
        return []
    out = ["## Previous attempts on THIS goal", ""]
    for i, d in enumerate(deads, 1):
        out.append(context_files.render_attempt_block(i, d).rstrip())
        out.append("")
    return out


def _collect_lemma_names(deads: list[sqlite3.Row],
                        mfst: manifest.Manifest) -> list[str]:
    """Names visible to the agent: those Lean errored on (highest
    signal) plus those the Manifest curated. De-duped, first-seen order."""
    names: list[str] = []
    seen: set[str] = set()
    for d in deads:
        for nm in lemma_lookup.extract_lemma_names(d["failure_detail"] or ""):
            if nm not in seen:
                seen.add(nm)
                names.append(nm)
    for hint in mfst.mathlib_hints:
        m = re.match(r"\s*([A-Z][\w']*(?:\.[\w']+)+)", hint)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            names.append(m.group(1))
    return names


def _fetch_strategy_dead_attempts(
    conn: sqlite3.Connection, goal_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT da.target_id, da.failure_reason, da.failure_detail,"
        "       da.pipeline_id, s.proposal_md AS strategy_proposal "
        "FROM dead_attempts da "
        "JOIN strategies s ON s.id = da.target_id "
        "WHERE da.target_kind = 'Strategy' AND s.goal_id = ? "
        "ORDER BY da.id DESC LIMIT 5",
        (goal_id,),
    ).fetchall()


def _fetch_dead_strategies(
    conn: sqlite3.Connection, goal_id: int, *, k: int = 5,
) -> list[dict]:
    """F37 — strategies that were proposed for this goal but later died
    (sub-goal cascade-shelve, F16 inward kill, etc). Each result
    includes the strategy's proposal_md plus the slug+statement of
    every sub-goal it spawned, so the next Backward can be told 'these
    decompositions were tried and failed — pick a different angle.'
    Filtered to strategies with non-empty proposal_md AND ≥ 1 linked
    sub-goal — drops half-baked recovery cleanups (status='dead' +
    empty proposal) which carry no signal."""
    rows = conn.execute(
        "SELECT s.id, s.proposal_md FROM strategies s "
        "WHERE s.goal_id = ? AND s.status = 'dead' "
        "  AND s.proposal_md != '' "
        "  AND EXISTS (SELECT 1 FROM strategy_subgoals ss "
        "              WHERE ss.strategy_id = s.id) "
        "ORDER BY s.id DESC LIMIT ?",
        (goal_id, k),
    ).fetchall()
    out: list[dict] = []
    for r in rows:
        subs = conn.execute(
            "SELECT g.slug, g.statement, g.status FROM strategy_subgoals ss "
            "JOIN goals g ON g.id = ss.subgoal_id "
            "WHERE ss.strategy_id = ? ORDER BY ss.position ASC",
            (int(r["id"]),),
        ).fetchall()
        out.append({
            "id": int(r["id"]),
            "proposal_md": r["proposal_md"],
            "subs": [(s["slug"], s["statement"], s["status"]) for s in subs],
        })
    return out


def _fetch_builder_declines(
    conn: sqlite3.Connection, goal_id: int, *, k: int = 3,
) -> list[sqlite3.Row]:
    """F48 — Builder decline events on this goal."""
    return conn.execute(
        "SELECT proposal_md, ts FROM dead_attempts "
        "WHERE target_id = ? AND target_kind = 'Goal' "
        "  AND failure_reason = 'agent_declined' "
        "  AND COALESCE(proposal_md, '') != '' "
        "ORDER BY id DESC LIMIT ?",
        (goal_id, k),
    ).fetchall()


def _section_builder_declines(rows: list[sqlite3.Row]) -> list[str]:
    """F48 — render Builder decline reasons inline so Backward sees
    *what specifically* the Builder agent flagged as hard."""
    if not rows:
        return []
    out = [
        "## Why Builder declined this goal",
        "",
        "Earlier Builder attempts on this goal followed the decline "
        "hatch (wrote PROPOSAL.md, no patch.lean) instead of producing "
        "a guess. Their reasoning is below — design the decomposition "
        "to address the specific hard parts they identified.",
        "",
    ]
    for i, r in enumerate(rows, 1):
        body = (r["proposal_md"] or "").strip()
        out.append(f"### Decline {i}")
        out.append(body)
        out.append("")
    return out


def _section_library_available(mfst, workspace) -> list[str]:
    """F49 — list Library/<Topic>/INDEX.md entries for the topics
    inferred from `mfst.lemma_hints` (any `Library.<Topic>.*` entries)."""
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


def _section_dead_strategies(rows: list[dict]) -> list[str]:
    """F37 — anti-repetition hint for sequential Backward retry."""
    if not rows:
        return []
    out = [
        "## Prior strategies that died (avoid re-proposing the same shape)",
        "Earlier Backward attempts for this same goal produced the "
        "decompositions below. Each one was killed because at least one "
        "of its sub-goals could not be proved (cascade-shelve). Do NOT "
        "re-propose a decomposition that hinges on the same dead "
        "sub-goal — pick a structurally different angle.",
        "",
    ]
    for i, s in enumerate(rows, 1):
        out.append(f"### Dead strategy s{s['id']}")
        out.append("Sub-goals it produced:")
        for slug, statement, status in s["subs"]:
            mark = "(shelved)" if status == "shelved" else f"({status})"
            stmt = statement.strip().splitlines()[0][:200]
            out.append(f"- `{slug}` {mark} — {stmt}")
        out.append("")
    return out


def _section_past_backward(rows: list[sqlite3.Row]) -> list[str]:
    """F43 + F55 — full inline rendering of past-Backward history.

    Renders sibling strategies' Verify failures so the agent avoids
    re-proposing a decomposition with the same typing shape. The
    companion file `PAST_BACKWARD.md` (formerly PAST_VERIFIES.md)
    carries the same content + an additional partial-PROPOSAL section
    when applicable; this inline copy keeps the must-see signal in
    front of the agent without forcing a Read tool round-trip."""
    if not rows:
        return []
    out = [
        "## Past decompositions that failed Verify",
        "",
        "Earlier Backward attempts decomposed this goal but the "
        "combination patch did not elaborate against the sub-goal "
        "proofs. Each block below is the lake stderr + the "
        "strategy's PROPOSAL.md. Avoid re-proposing a decomposition "
        "with the same typing shape.",
        "",
    ]
    for i, r in enumerate(rows, 1):
        out.append(context_files.render_strategy_block(i, r).rstrip())
        out.append("")
    return out


def _section_prior_partial(kind: str | None, problem_dir: Path,
                           goal_id: int) -> list[str]:
    """F55 — surface the postmortem progress note (if any) from a
    prior timed-out spawn on THIS (goal, kind) pair. The note is the
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

    `kind` (F43): 'builder' | 'backward' | None.
      - 'builder'  → render PAST_ATTEMPTS section, skip PAST_BACKWARD
      - 'backward' → render PAST_BACKWARD section, skip PAST_ATTEMPTS
      - None       → render both (back-compat for tests)
    Each kind only sees the failure history it can actually act on:
    Builder fixes leaf-level patches, Backward fixes decomposition
    shape; cross-feeding adds noise without signal.

    F55 — also surfaces the persisted partial output (PROPOSAL.md for
    backward, patch.lean for builder) from a prior failed/timed-out
    spawn, so the agent picks up where it left off instead of starting
    fresh.

    Section ordering — keep stable; agents may have learned to scan
    top-down. Each section function returns `[]` when not applicable
    so the resulting Context.md only contains sections with content.
    """
    workspace = attempts_dir.parent.parent  # .attempts/<pid> → workspace
    problem_dir = workspace / "Problems" / goal["problem"]
    deads = db.recent_dead_attempts(
        conn, target_id=goal["id"], target_kind="Goal", k=5)
    strat_deads = _fetch_strategy_dead_attempts(conn, int(goal["id"]))
    dead_strats = _fetch_dead_strategies(conn, int(goal["id"]))
    builder_declines = (
        _fetch_builder_declines(conn, int(goal["id"]))
        if kind == "backward" else []
    )

    show_attempts = kind in (None, "builder")
    show_verifies = kind in (None, "backward")

    # P0-#4: gate the dedupe on `show_verifies`. Builder kind suppresses
    # the verify-failures section; applying the dedupe there would
    # silently strip dead-strategy signal too.
    if show_verifies:
        verify_failed_strategy_ids: set[int] = set()
        for r in strat_deads:
            try:
                verify_failed_strategy_ids.add(int(r["target_id"]))
            except (KeyError, IndexError, TypeError):
                pass
        dead_strats_filtered = [
            s for s in dead_strats
            if s["id"] not in verify_failed_strategy_ids
        ]
    else:
        dead_strats_filtered = dead_strats

    sections: list[list[str]] = [
        _section_header(goal),
        _section_sandbox(strategy_id, goal),
        _section_strategy_naming(strategy_id, goal),
        _section_parent_strategy(conn, goal),
        _section_mathlib_lemmas(mfst, deads, workspace),
        _section_manifest_forbidden(mfst),
        _section_manifest_notes(mfst),
        _section_library_available(mfst, workspace),
        _section_playbook(goal, workspace),
        _section_builder_declines(builder_declines),
        _section_prior_partial(kind, problem_dir, int(goal["id"])),
        _section_past_attempts(deads) if show_attempts else [],
        _section_past_backward(strat_deads) if show_verifies else [],
        _section_dead_strategies(dead_strats_filtered),
    ]

    parts: list[str] = []
    for section in sections:
        parts.extend(section)

    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")

    # F26 — write companion reference files for the bulky / lazy-load
    # content (Context.md only carries digests + pointers). F55 — the
    # progress note from a prior timed-out spawn is rendered ONLY in
    # Context.md (must-see channel), not duplicated into the companion
    # — agents miss companion files (F43) so the inline section is the
    # canonical surface.
    context_files.write_past_attempts(deads, attempts_dir)
    context_files.write_past_backward(strat_deads, attempts_dir)

    return out
