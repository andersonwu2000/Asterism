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


def write_context_stats(attempts_dir: Path, *, label: str,
                        names: "list[str]",
                        sections: "list[list[str]]") -> None:
    """Context telemetry (task #7): per-section weights — one compact log
    line for live monitoring + `_context_stats.json` in the attempts dir,
    which WorkArea packs into dead_attempts.artifacts, so the numbers ride
    the existing forensic channel with no schema change. Every past
    context diet (the Forward-TREE 400-line cut, the 76%-noise failure
    digest) was post-hoc archaeology; this makes section weight a standing
    metric. Best-effort: never fails the compile."""
    import json as _json
    try:
        stats = []
        for name, lines in zip(names, sections):
            if not lines:
                continue
            nbytes = sum(len(ln) + 1 for ln in lines)
            stats.append({"section": name, "lines": len(lines),
                          "bytes": nbytes})
        total = sum(s["bytes"] for s in stats)
        (attempts_dir / "_context_stats.json").write_text(
            _json.dumps({"label": label, "total_bytes": total,
                         "sections": stats}), encoding="utf-8")
        top = sorted(stats, key=lambda s: s["bytes"], reverse=True)[:4]
        print(f"[context] {label}: {total}B total; top: "
              + ", ".join(f"{s['section']}={s['bytes']}B" for s in top),
              flush=True)
    except (OSError, ValueError):
        pass


# ---------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------

def goal_display_signature(workspace: Path, slug: str,
                           lean_path: "str | None",
                           statement: "str | None") -> str:
    """Full binders+conclusion display form for a goal (#5, user call
    2026-07-18): `goals.statement` stores the bare conclusion — a
    by_contra sub-goal reads as just `False` — while the on-disk stub
    carries the whole signature. Read it CATALOG-style; fall back to
    the stored statement. Display-only: dedupe keeps matching on the
    statement column."""
    if lean_path:
        try:
            text = (workspace / str(lean_path)).read_text(encoding="utf-8")
            sig = _decl_signature(text, slug)
            if sig:
                return " ".join(sig.split())
        except OSError:
            pass
    return str(statement or "")


def _section_header(goal: sqlite3.Row, workspace: Path) -> list[str]:
    return [
        f"# Context for goal {goal['slug']}",
        "",
        "## Goal statement",
        goal_display_signature(workspace, str(goal["slug"]),
                               goal["lean_path"], goal["statement"]),
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
        "- `PAST_*.md` / `LESSONS.md` / `CATALOG.md` / `PAPER_MAP.md` / "
        "`BATCHES.md` sit in Context.md's own directory (NOT your cwd) "
        "and are read-only. `CATALOG.md` holds the exact statement of "
        "every proved brick in this problem — read it before citing one.",
        "- `patch.lean` is your output; sub-goal stubs go in "
        "`new_<slug>.lean`. Lead with `--` annotation comments, then edit "
        "the body — the signature is locked. See your prompt for layout.",
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
                             goal: sqlite3.Row,
                             workspace: Path) -> list[str]:
    if goal["origin"] != "backward":
        return []
    row = conn.execute(
        "SELECT g.slug AS parent_slug, g.statement AS parent_statement,"
        "       g.lean_path AS parent_lean_path,"
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
    parent_sig = goal_display_signature(
        workspace, str(row["parent_slug"]), row["parent_lean_path"],
        row["parent_statement"])
    out = [
        "## Parent goal & strategy",
        f"This goal `{goal['slug']}` is a sub-goal of "
        f"`{row['parent_slug']}`:",
        "",
        f"> {parent_sig}",
        "",
    ]
    if row["proposal_md"]:
        out.extend([
            # Do NOT name a file here. This text comes from
            # `strategies.proposal_md`, a DB column — and the label used
            # to call it "parent's PROPOSAL.md excerpt", so workers went
            # looking for a PROPOSAL.md in their own attempts dir and
            # found nothing: v33 merged every worker kind into the
            # Formalizer, whose output is patch.lean + new_*.lean.
            # Measured 2026-08-10: four such reads across four pipelines,
            # one wasted turn each.
            "Strategy that produced this sub-goal "
            "(the parent worker's own rationale):",
            "```",
            row["proposal_md"][:2000],
            "```",
            "",
        ])
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
    # Empty list still renders — the prompts reference this section
    # unconditionally, and a silently absent heading left agents unsure
    # whether the list was empty or the Context truncated
    # (agent_feedback 2026-07-12..13).
    if not mfst.forbidden_lemmas:
        return ["## FORBIDDEN_LEMMAS (from Manifest.md)", "(none)", ""]
    return [
        "## FORBIDDEN_LEMMAS (from Manifest.md)",
        "**Do NOT use any of the following in your proof or in any "
        "sub-goal docstring; the integrator will reject the proposal.**",
        *(f"- {f}" for f in mfst.forbidden_lemmas),
        "",
    ]


def _section_manifest_body(mfst: manifest.Manifest) -> list[str]:
    """The operator's Manifest, whole (2026-08-11).

    It used to be one extracted section, `## Strategic notes`. The
    framework no longer reads headings in this file — an operator writes
    what they like there and the machine cannot promise to find a name
    it chose. Whole is also cheap: median body across 616 Manifests is
    440 B, p90 1,066 B. And it makes the operator's steering channel
    stronger rather than weaker — anything written in the file reaches
    the agent, not only the paragraph under one blessed heading."""
    if not mfst.body:
        return []
    return [
        "## Manifest (from the operator)",
        "",
        mfst.body,
        "",
    ]


# ---------------------------------------------------------------------
# Failure digest helpers (used by Context summary + tests)
# ---------------------------------------------------------------------

#: The framework's own exit-code preamble on a spawn autopsy
#: (`agent rc=124` / `rc=124`) — never the reason for anything.
_RC_PREAMBLE_RE = re.compile(r"^(agent\s+)?rc=-?\d+\s*$", re.IGNORECASE)
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
        # Skip our own exit-code preamble. On a timeout the first two
        # lines are `agent rc=124` / `rc=124` and the third is the
        # salvage verdict — which is the whole story (did the spawn die
        # holding a complete proof, a missing comment header, or a
        # gateway 404?). Returning line one made every timeout read
        # identically. These prefixes are framework-emitted, not agent
        # prose: matching our own format is reading structure.
        for line in failure_detail.strip().splitlines():
            s = line.strip()
            if not s or _RC_PREAMBLE_RE.match(s):
                continue
            return s[:200]
        return ""

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
    cross-spawn stable context — sandbox / forbidden /
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


CATALOG_COMPANION = "CATALOG.md"
PAPER_MAP_COMPANION = "PAPER_MAP.md"

# Display-grade signature extraction for the catalog (2026-07-13, user
# call: `goals.statement` on a Backward sub-goal is the bare conclusion
# — binders and hypotheses live only in the proof file, so the catalog
# showed `(f.comp γ).Nullhomotopic` with no premises). NOT a soundness
# surface: parsing is best-effort, fallback = the bare statement.
_ALIAS_TARGET_RE_TMPL = r"def\s+{slug}\b[^\n]*:=\s*@[\w.]*?\.(s\d+)"


def _decl_signature(text: str, name: str) -> "str | None":
    """The declaration block for `name` from `:  = by` (exclusive) —
    attributes/noncomputable prefixes included, proof body excluded.
    A body-only decl (data def, no tactic block) keeps its body up to
    the cap: for those the body IS the information."""
    m = re.search(
        r"^(?:@\[[^\]]*\]\s*)?(?:noncomputable\s+)?(?:private\s+)?"
        r"(?:theorem|lemma|def|abbrev|instance|structure|class|inductive)\s+"
        + re.escape(name) + r"\b", text, re.M)
    if m is None:
        return None
    block = text[m.start():]
    cut = re.search(r":=\s*by\b", block)
    if cut is not None:
        block = block[:cut.start()]
    else:
        end = re.search(r"^end\b", block, re.M)
        if end is not None:
            block = block[:end.start()]
    # No cap. CATALOG.md IS the lazily-loaded layer — the file an agent
    # opens only when it needs the exact statement — so truncating
    # inside it pays a long quotation's budget and delivers a short
    # one's reliability (operator ruling, the same one BATCHES.md was
    # built on). The old 1500-char cut landed mid-word and sent workers
    # to the .lean file anyway, which is the hop the companion exists
    # to remove.
    return block.strip()


def _catalog_signature(workspace: Path, lean_path: str,
                       slug: str) -> "str | None":
    try:
        text = (workspace / lean_path).read_text(encoding="utf-8")
    except OSError:
        return None
    alias = re.search(_ALIAS_TARGET_RE_TMPL.format(slug=re.escape(slug)),
                      text)
    if alias is not None:
        sid = alias.group(1)
        try:
            text = ((workspace / lean_path).parent
                    / f"_strategy_{sid}.lean").read_text(encoding="utf-8")
        except OSError:
            return None
        sig = _decl_signature(text, sid)
        # Print the CITABLE head, not the alias target's `s<N>`
        # (2026-08-07, user call). The block is what agents copy from,
        # and it read `theorem s24218 ...` under a `## bin_entropy_pair
        # _bound` heading whose own file header says "never cite the
        # inner s<N>" — 16 of 52 entries on Frankl, and the run's own
        # Programme wrote "bin_entropy_pair_bound (theorem s24218)"
        # off it and was rebutted. `def <slug> := @<sid>` makes the two
        # definitionally the same statement, so swapping the head keeps
        # the signature true while making it copy-safe.
        if sig is not None:
            sig = re.sub(r"\b" + re.escape(sid) + r"\b", slug, sig, count=1)
        return sig
    return _decl_signature(text, slug)


def alive_goal_rows(conn: sqlite3.Connection,
                    problem: str) -> list[sqlite3.Row]:
    """The problem's ALIVE goals (open / attempting / awaiting review).

    Single home for the catalog's alive query: the companion renders
    them and callers gate their pointer surfaces on the same rows."""
    return list(conn.execute(
        "SELECT slug, statement, kind, lean_path FROM goals"
        " WHERE problem = ? AND status IN"
        " ('open','attempting','pending_strategist_review')"
        " ORDER BY id", (problem,)))


def write_catalog_companion(conn: sqlite3.Connection, problem: str,
                            attempts_dir: Path,
                            workspace: "Path | None" = None,
                            ) -> list[sqlite3.Row]:
    """`CATALOG.md` — the problem's proved-brick catalog, machine-
    generated from goal records (2026-07-13, user call): slug + exact
    statement + kind + proof file for every proved goal.

    This is the citation SoT the Strategist previously hand-maintained
    inside the standing directive (26KB on simple_loop, re-sent to
    every worker on every spawn, and burned by pipeline renames four
    times because it was a hand-copy). Generated from the same rows the
    pipelines landed, it can never drift. Inline surfaces carry only
    slugs / curated subsets; exact statements are read here on demand —
    the same lazy pattern as `LESSONS.md` / `PAST_*.md`.

    `workspace` must be passed when `attempts_dir` is not the standard
    `<workspace>/.attempts/<pid>` layout (the adversary projection dir).

    Returns the proved rows (empty when nothing proved or the write
    failed — callers render no section in that case). The FILE is
    written whenever the problem has proved OR alive goals: the alive
    block is mint's dedupe surface, and gating the write on proved
    rows alone deleted it exactly when the problem was youngest — the
    prompts' "check `## Alive goals` in CATALOG.md" then pointed at a
    file that did not exist (07-29 mint feedback)."""
    rows = list(conn.execute(
        "SELECT slug, statement, kind, lean_path FROM goals"
        " WHERE problem = ? AND status = 'proved' ORDER BY id",
        (problem,)))
    alive = alive_goal_rows(conn, problem)
    if not rows and not alive:
        return []
    if workspace is None:
        workspace = attempts_dir.parent.parent
    lines = [
        f"# Proved catalog — {problem} ({len(rows)} entries)",
        "_Machine-generated from the framework's goal records on every"
        " spawn; always matches what actually landed. Each entry carries"
        " the exact import line and the name to cite (the file's inner"
        " `s<N>` head is an internal alias target — never cite it)._",
        "",
    ]
    # Alive goals up top (user call 2026-07-19): the mint rule
    # "a statement matching an ALIVE in-problem Goal is discarded —
    # decline and name it" was unenforceable with no list to check
    # (a5 run ×4); same grep motion as a citation lookup, so it lives
    # in the same file. Not mintable; CITABLE since task #123 (the
    # commit gate registers a wait edge).
    if alive:
        lines += [
            f"## Alive goals ({len(alive)} — OPEN, in flight)",
            "_A minted lemma matching one of these is discarded by"
            " dedupe — decline and name the goal instead. Citing one"
            " is legal: it auto-links and your strategy waits for it._",
            "",
        ]
        for a in alive:
            # `goals.statement` is the conclusion only (sig_conclusion,
            # dedupe's matching key) — the cite-vs-fresh decision needs
            # the hypotheses, so read the full signature off the stub
            # file like the proved entries do (07-19 feedback ×6).
            sig = (_catalog_signature(workspace, str(a["lean_path"] or ""),
                                      str(a["slug"]))
                   or str(a["statement"] or ""))
            stmt = " ".join(sig.split())
            lines.append(f"- `{a['slug']}` ({a['kind']}): `{stmt}`")
        lines.append("")
    for r in rows:
        slug = str(r["slug"])
        sig = (_catalog_signature(workspace, str(r["lean_path"]), slug)
               or str(r["statement"]).strip())
        mod = str(r["lean_path"]).replace("\\", "/")
        if mod.endswith(".lean"):
            mod = mod[:-len(".lean")].replace("/", ".")
        lines += [
            f"## {slug}  ({r['kind']})",
            "```lean",
            sig,
            "```",
            # a5 run ×4: citing a brick cost a directory hunt because
            # the module path and citable name lived only on disk
            f"cite `{slug}` — `import {mod}`",
            "",
        ]
    try:
        (attempts_dir / CATALOG_COMPANION).write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        return []
    return rows


def catalog_companion_path(attempts_dir: Path) -> str:
    """Where `CATALOG.md` actually is, absolute.

    "read-only companion beside this Context.md" was true and still cost
    five workers a directory hunt in one run (2026-08-06 feedback: "did
    not exist in the working directory", "forced a blind grep of
    proofs/", "two wasted find calls"): the worker's cwd is the PROBLEM
    dir, the companion sits in the attempts dir, and resolving "beside"
    means joining a path the agent only ever saw in its spawn header.
    Print the path instead of describing it."""
    return (attempts_dir / CATALOG_COMPANION).as_posix()


def _section_catalog_pointer(conn: sqlite3.Connection, problem: str,
                             attempts_dir: Path) -> list[str]:
    """Backward/Builder surface: two-line pointer only. These workers
    already get a per-goal curated citation surface (pre-search); the
    companion is their exact-statement lookup, not another list."""
    rows = write_catalog_companion(conn, problem, attempts_dir)
    if not rows:
        return []
    return [
        "## Proved catalog",
        f"_All {len(rows)} proved bricks of this problem are citable;"
        f" exact statements live in `{catalog_companion_path(attempts_dir)}`"
        " (read-only; NOT in your cwd). Read an entry there"
        " BEFORE citing it — never"
        " re-derive a landed brick. Pre-search candidates (when"
        " present) are the curated subset for THIS goal._",
        "",
    ]


def _kb_entry_lines(r: sqlite3.Row) -> list[str]:
    """One KB entry as a bullet (title) plus any body lines indented beneath."""
    lines = [f"- {(r['title'] or '').strip()}"]
    body = (r["body"] or "").strip()
    if body:
        lines += [f"  {bl}" for bl in body.splitlines()]
    return lines


def _section_lessons_inline(conn: sqlite3.Connection, problem: str,
                            goal_id: int | None = None,
                            attempts_dir: Path | None = None) -> list[str]:
    """Inline this problem's KB knowledge — GLOBAL lessons (cross-goal insights)
    + antipatterns (walls hit on THIS goal). Sourced from `kb_entries`.

    Titles-index + on-demand bodies (2026-07-05, user design call): lessons
    inline as ONE title line each (`[id-N]` cue); full bodies go to the
    `LESSONS.md` companion in attempts_dir, read on demand — the same
    pattern as `PAST_*.md`. Global lessons are problem-wide while relevance
    is per-goal: a multi-front problem (sphere_homology: 21 lessons / 27KB,
    ~2 relevant per goal) made full inline the largest context section and
    a thinking-trap risk (stokes 4284 class). This differs from the RETIRED
    `KB_LESSONS` grep-file (~1% usage): that had no inline cue at all —
    here every title stays in context as the cue, only the body moves.

    Antipatterns stay full-inline: node-bound, surfaced only to their own
    goal (`kb.query` filters), so they are already relevance-scoped.

    Fallback: no `attempts_dir` (legacy/odd caller) → full inline as before.
    Global-only (2026-06-28): node-bound lessons retired; legacy node rows
    are excluded by `kb.query`."""
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
            "_Cross-cutting insights recorded by past agents on this problem._",
        ]
        if attempts_dir is not None:
            out += [
                "_Titles only — the full recipes (exact lemma names, gotchas)"
                " live in `LESSONS.md` (read-only companion). Read an entry's"
                " body BEFORE using or re-deriving its technique._",
                "",
            ]
            body_lines = [f"# Lessons — full recipes ({problem})", ""]
            for r in lessons:
                out.append(f"- [id-{r['id']}] {(r['title'] or '').strip()}")
                body_lines += [f"## [id-{r['id']}] "
                               f"{(r['title'] or '').strip()}", ""]
                body = (r["body"] or "").strip()
                if body:
                    body_lines += [body, ""]
            try:
                (attempts_dir / "LESSONS.md").write_text(
                    "\n".join(body_lines) + "\n", encoding="utf-8")
            except OSError:
                pass  # index still useful without the companion
        else:
            out.append("_Maintained by the reflection spawn._")
            out.append("")
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
        "with a leading `--` summary — proofs lead with "
        "`-- <slug>: <summary>`, decompositions with a `--` "
        "rationale block.")
    lines.append("")
    return lines


def _section_library_available(conn, mfst) -> list[str]:
    """Surface the reusable Library — theorems Asterism already proved and
    harvested from prior Problems — to the PROVING agent, so it can cite
    them instead of re-deriving (Library-as-input).

    v18: rendered from the DB (`db.bridged_library_index` — bridged
    problems' placed decls; was: parsing INDEX.md sections). Same COMPACT
    menu, domain-filtered (a `LinearAlgebra.*` problem sees the
    `LinearAlgebra.*` Library). The agent has read access to `Library/` —
    it greps there for exact signatures (its real discovery interface,
    unchanged; agents grep the whole tree, wider than this menu); the menu
    just tells it what exists and how to cite. Returns [] when the Library
    has nothing relevant (keeps unrelated problems' Context clean)."""
    if conn is None:
        return []          # conn-less render (brief in bare tests)
    sections = [
        (prob, [str(r["target_name"] or r["slug"]) for r in rows])
        for prob, rows in db.bridged_library_index(conn).items()]
    if not sections:
        return []

    problem = mfst.problem or ""
    domain = problem.split(".")[0] if "." in problem else problem
    relevant = [(p, d) for p, d in sections
                if d and (p.split(".")[0] == domain)]
    if not relevant:
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
    if relevant:
        out.append(f"Library modules in the `{domain}` domain "
                   "(grep `Library/` for signatures):")
        for p, d in relevant:
            keystone = next((x for x in d if x.endswith(".main")), None)
            tag = f" — keystone `{keystone}`" if keystone else ""
            out.append(f"- **{p}** ({len(d)} decls){tag}")
        out.append("")
    return out


def _note_title(note: str) -> str:
    """The note's own first non-blank line, as its label.

    Not an extraction: `force_progress.md` asks for a title line first,
    and this reads the line the writer put first — the same convention
    `formalize.md` already uses for the commit header. When a note
    arrives without one, its opening line is still the best label
    available, and a bad label costs a pointer follow, not a fact."""
    for ln in str(note or "").splitlines():
        s = ln.strip().lstrip("#").strip()
        if s:
            return s[:120]
    return ""


def _render_attempt_digest(idx: int, dead, *, note_in_full: bool) -> str:
    """One attempt as Context.md carries it: what failed, in one line,
    plus the parting note for the most recent attempt only. The full
    autopsy — raw failure_detail, PROPOSAL.md, every note — is in
    `PAST_DIRECT_ATTEMPTS.md`, which the umbrella header names."""
    out = [f"### Attempt {idx} ({str(dead['pipeline_id'])[:12]}): "
           f"{dead['failure_reason']}"]
    digest = _digest_failure(str(dead["failure_reason"] or ""),
                            str(dead["failure_detail"] or ""))
    if digest:
        out += ["", digest]
    note = context_files._agent_note_from_artifacts(dead)
    if note:
        if note_in_full:
            out += ["", "Agent note (its own `_progress.md`, written as "
                    "the attempt ended):", "```", note, "```"]
        else:
            title = _note_title(note)
            out += ["", f"Agent note: {title} — in "
                    f"`{context_files.PAST_DIRECT_ATTEMPTS_FILENAME}`"]
    return "\n".join(out)


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
                "Note: blocks with `agent_declined` are a worker declining "
                "this goal as decomposition-needed (PROPOSAL.md carries "
                "the specific hard parts identified). Design the "
                "decomposition to address them."
            )
            sub.append("")
        # Inline gets the DIGEST; the full block goes to the companion
        # file. Both were already specified that way — `write_past_attempts`
        # tells its reader "Context.md shows a 1-line digest per attempt",
        # and `_agent_note_from_artifacts` says it renders "in this LAZY
        # file only" — but one renderer served both audiences, so every
        # attempt shipped its whole autopsy AND its whole parting note
        # inline. Measured on g7491 (5 attempts): 10,527 B, most of it a
        # verbatim second copy of the companion file.
        #
        # The newest attempt keeps its note in full: that one is the
        # hand-off ("patch.lean is ~525 lines and structurally complete;
        # here is the uniform fix"), and it is the reason the next spawn
        # does not start over. Older notes collapse to their own first
        # line — the title the postmortem prompt asks for — plus the
        # pointer. A title is not a summary the framework invented; it is
        # what the writer put first.
        for i, d in enumerate(direct_events, 1):
            sub.append(_render_attempt_digest(i, d, note_in_full=(i == 1)))
            sub.append("")
        parts.append(sub)

    if show_verifies and verify_events:
        sub = [
            "### Sibling decompositions that failed Verify",
            "",
            "Earlier attempts decomposed this goal but the "
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
            "Earlier attempts produced the decompositions below "
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
    intact, refactor, or discard. Backward (2026-07-06, timeout-fallback
    salvage) gets it too, with a caveat: its patch declares the PRIOR
    strategy's `s<id>` token, which the fresh skeleton has re-minted —
    the material is a clue, never a verbatim copy source.
    """
    if kind not in ("builder", "backward"):
        return []
    try:
        from ..pipeline import _drafts
    except ImportError:
        return []
    body = _drafts.read_partial_patch(
        problem_dir=problem_dir, kind=kind, goal_id=goal_id)
    if not body:
        return []
    caveat = (
        [] if kind == "builder" else
        ["NOTE: it declares the previous strategy's `s<id>` name — your "
         "skeleton has a NEW one. Reuse ideas/lemmas, not the header.",
         ""])
    return [
        "## Your previous patch.lean attempt (unverified)",
        "",
        "A prior spawn on this goal was interrupted before its "
        "patch.lean could be promoted to the workspace. The body "
        "below is what that spawn last wrote. It may be a complete "
        "proof, a partial sketch, or a wrong direction — and names "
        "it references may be PROPOSED sub-goals that never landed. "
        "Treat as a starting point, validate via the LSP before "
        "relying on it.",
        "",
        *caveat,
        "```lean",
        body.rstrip(),
        "```",
        "",
    ]


# ---------------------------------------------------------------------
# Phase 2 — Strategist directive / brief sections
# ---------------------------------------------------------------------

def _section_programme_worker(conn: sqlite3.Connection, problem: str,
                              decision_id: "int | None",
                              problem_dir: "Path | None" = None,
                              goal_id: "int | None" = None,
                              ) -> list[str]:
    """NL-first worker premise (2026-07-25, user call — b6_1 leg 7:
    workers minted a d5-d13 variant mill because they could not SEE the
    argued mathematics): the worker's share of the Programme is the
    `## Proof` itself, in full — batch-scoped, so it stays small. One
    pointer covers the rest; it resolves because PROGRAMME.md sits in
    the problem dir (spawn cwd, inside the Read allowlist)."""
    from ..state import programme as _programme
    from ..state import groups as _groups
    try:
        # The rev that AUTHORISED this goal, not the latest one — see
        # `programme.rev_for_goal`. A sibling branch's review can ship a
        # new rev while this branch's sub-goals are still being
        # auto-dispatched; reading the current rev then hands the worker
        # an argument that never justified its goal.
        row = _programme.rev_for_goal(conn, problem, goal_id=goal_id,
                                      decision_id=decision_id)
    except sqlite3.OperationalError:
        return []
    if row is None:
        return []
    # v35 — revision chains are PER GROUP, each numbered from 1. "Has
    # the Programme moved on?" is only meaningful within the goal's own
    # chain: comparing against the problem-wide max rev told a
    # sub-group's worker its (only) rev had been superseded by the TOP
    # group's chain (SLC 08-04: goal 7309, group 370 rev 1, reported
    # against group 368's rev 27 — #164).
    try:
        gid = row["group_id"]
    except (IndexError, KeyError):
        gid = None
    try:
        current = _programme.current_rev(conn, problem, gid)
        top = _groups.top_group(conn, problem)
    except sqlite3.OperationalError:
        current, top = None, None
    top_id = int(top["id"]) if top is not None else None
    # The group's own render target — the TOP group keeps PROGRAMME.md
    # in the problem dir; sub-groups render under .groups/<id>/ (both
    # inside the worker's Read allowlist, cwd = problem dir).
    prog_rel = _programme.PROGRAMME_BASENAME
    if gid is not None and top_id is not None and int(gid) != top_id:
        prog_rel = f".groups/{int(gid)}/{_programme.PROGRAMME_BASENAME}"
    # The pointer must resolve (design §2 P1 acceptance point): the
    # pass-commit render is best-effort, so a fresh checkout / failed
    # render can leave a rev in the DB with no file on disk. Re-render
    # idempotently before advertising it.
    if problem_dir is not None and not (problem_dir / prog_rel).exists():
        try:
            _programme.render(conn, problem, problem_dir, gid)
        except OSError:
            pass
    # The whole `## Proof` rides inline only when nothing more specific
    # answered. When the brick has its own argument — the passage its
    # author copied into the Inject — that passage IS this section's
    # job, and the rest of the batch is other bricks' business: g7509
    # carried 10,160 B of five-section Proof with no line anywhere
    # saying which section was its own.
    has_own = bool(authorising_proof(conn, decision_id, goal_id)[0])
    sections, _err = _programme.parse_proposal(str(row["body"] or ""))
    proof = ((sections or {}).get("proof") or "").strip()
    out = [f"## Proof (Programme rev {row['rev']})", ""]
    if proof and not has_own:
        out += [proof, ""]
    # PROGRAMME.md on disk always renders the group's CURRENT rev. When
    # that is not the rev above, say so rather than let the pointer
    # quietly substitute a different argument for the one that
    # authorised this goal — the same drift this section was just
    # pinned against.
    if current is not None and int(current["rev"]) != int(row["rev"]):
        # The race actually happening, on the record. Silence here means
        # the Programme never moved under anyone's feet in this run;
        # a line means it did, and names who was riding the old argument.
        print(f"[programme-pin] goal {goal_id}: authorised by rev "
              f"{row['rev']}, current is {current['rev']}"
              f" (group {gid})", flush=True)
        # The stamp is the whole point of this branch and it must not go
        # with the text it used to annotate: a worker on attempt 4 of a
        # stale line has no other way to know its argument is a fossil.
        anchor = ("The argument above" if not has_own
                  else "The argument for this brick")
        out += [f"Full Programme: `{prog_rel}` beside the problem "
                f"files — note it renders rev {current['rev']}, which has "
                f"moved on from the rev that authorised this goal. "
                f"{anchor} is the one you formalize against.", ""]
    else:
        out += [f"Full Programme (Argument / Roadmap / adversary "
                f"reservations): `{prog_rel}` beside the problem files.",
                ""]
    return out


def _section_strategist_directive(conn: sqlite3.Connection,
                                  problem: str,
                                  goal_id: "int | None" = None) -> list[str]:
    """Standing worker guidance, from its two sources (2026-08-03,
    research_mission_design.md §3.1):

      1. the owning group chain's `## Conventions` Programme sections
         (top group first, nearest group last) — the successor of the
         retired `EmitDirective`;
      2. `problems.strategist_directive` — now the OPERATOR/legacy note
         channel only (`reject-ingest` writes here; the strategist can
         no longer). Rendered under its old header while non-empty.

    Both conditional on content; either may be absent."""
    out: list[str] = []
    try:
        from ..state import programme as _programme
        from ..state import groups as _groups
        row = (_groups.group_for_goal(conn, problem, int(goal_id))
               if goal_id is not None else None)
        gid = int(row["id"]) if row is not None else None
        conv = _programme.conventions_for_group(conn, problem, gid)
    except Exception:
        conv = ""
    if conv:
        out += ["## Conventions (standing)", "", conv, ""]
    try:
        row = conn.execute(
            "SELECT strategist_directive FROM problems WHERE name = ?",
            (problem,),
        ).fetchone()
    except sqlite3.OperationalError:
        # Pre-Phase 2 schema (column missing).
        return out
    if row is None:
        return out
    directive = row["strategist_directive"]
    if directive is None or not str(directive).strip():
        return out
    out += ["## Strategist directive", "", str(directive).strip(), ""]
    return out


#: The argument that authorised a goal, resolved most-specific-first —
#: the same walk `programme.rev_for_goal` uses for the revision, and for
#: the same reason. A worker that created its own sub-goals has no
#: decision of its own; it inherits the argument its parent was
#: dispatched under, and the walk goes up through `strategies`, not
#: through a bare goal-parent chain, so two live strategies on one OR
#: node never see each other's.
_AUTHORISING_PROOF_SQL = """
WITH RECURSIVE up(gid, depth) AS (
  VALUES(?, 0)
  UNION
  SELECT s.goal_id, up.depth + 1
    FROM strategy_subgoals ss
    JOIN strategies s ON s.id = ss.strategy_id
    JOIN up ON ss.subgoal_id = up.gid
)
SELECT d.brief AS proof, d.id AS decision_id FROM up
  JOIN strategist_decisions d
    ON CAST(d.produced_goal_id AS INTEGER) = up.gid
 WHERE d.brief IS NOT NULL AND TRIM(d.brief) <> ''
 ORDER BY up.depth ASC, d.id DESC
 LIMIT 1
"""


def authorising_proof(conn: sqlite3.Connection,
                      decision_id: "int | None" = None,
                      goal_id: "int | None" = None
                      ) -> "tuple[str, int | None]":
    """`(argument, decision_id)` for this piece of work, or `('', None)`.

    Empty is a real answer and the caller must handle it: a goal that
    predates the field, a revived or hand-detached node, a subtree whose
    injected ancestor left the field blank. On that path the worker gets
    the whole `## Proof` inline, which is what every worker got before
    this field existed — the fallback is the old behaviour, so nothing
    regresses while the tree fills in.
    """
    if decision_id is not None:
        try:
            row = conn.execute(
                "SELECT brief FROM strategist_decisions WHERE id = ?",
                (int(decision_id),)).fetchone()
        except sqlite3.OperationalError:
            return "", None
        if row is not None and str(row["brief"] or "").strip():
            return str(row["brief"]).strip(), int(decision_id)
    if goal_id is not None:
        try:
            row = conn.execute(_AUTHORISING_PROOF_SQL,
                               (int(goal_id),)).fetchone()
        except sqlite3.OperationalError:
            return "", None
        if row is not None:
            return str(row["proof"]).strip(), int(row["decision_id"])
    return "", None


def _section_strategist_brief(conn: sqlite3.Connection,
                              decision_id: int | None,
                              goal_id: "int | None" = None) -> list[str]:
    """The argument for THIS brick: the part of its batch's `## Proof`
    that settles it, which the author copied into the Inject when the
    batch was written and the Adversary judged along with it.

    Renders for auto-dispatched sub-goals too, via the ancestor walk —
    they are working inside the passage their parent was dispatched
    under, since a `## Proof` may carry no gaps and a decomposition
    therefore only outsources part of it.
    """
    proof, _ = authorising_proof(conn, decision_id, goal_id)
    if not proof:
        return []
    return [
        "## The argument for this brick",
        "",
        proof,
        "",
    ]


# ---------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------

# Hard presentation cap for the paper-index section. Shares the Context
# budget pool with the presearch candidates section (design note
# 2026-07-06): both are conditional surfaces; an over-cap map is a
# producer design problem (regenerate tighter), so truncation is LOUD.
PAPER_INDEX_MAX_CHARS = 8_000


def _paper_ids_for(mfst: manifest.Manifest, conn=None) -> list[str]:
    """Bound paper ids for the manifest's problem, primary first.
    Sources: DB `problem_papers` bindings (v2, D13) ∪ the legacy
    Manifest `paper:` pointer (always primary when present). conn=None
    (some test/offline callers) degrades to the Manifest pointer."""
    primary = (getattr(mfst, "paper", "") or "").strip()
    ids: list[str] = [primary] if primary else []
    if conn is not None:
        try:
            from ..state import db as _db
            for r in _db.paper_bindings(conn, str(mfst.problem)):
                if r["paper_id"] not in ids:
                    ids.append(str(r["paper_id"]))
        except Exception:  # noqa: BLE001 — bindings are additive, never break Context
            pass
    return ids


def _section_paper_index(mfst: manifest.Manifest,
                         workspace: Path, conn=None,
                         attempts_dir: "Path | None" = None) -> list[str]:
    """Paper navigation section — rendered when the problem binds ≥1
    shelved paper (Manifest `paper:` pointer ∪ DB bindings). The
    PRIMARY paper's map goes to the `PAPER_MAP.md` companion with a
    pointer inline (2026-07-14, user call: the static map repeated
    ~4KB into every context for 140+ wakes); auxiliary papers
    (scholar-fetched etc.) get one-line entries — their maps stay on
    disk, Read on demand (D14 budget bar). Original text is the
    content authority; this section only navigates (D1). No
    attempts_dir (legacy/odd caller) → full map inline as before."""
    pids = _paper_ids_for(mfst, conn)
    if not pids:
        return []
    from ..papers import shelf
    primary, aux = pids[0], pids[1:]
    meta = shelf.load_meta(workspace, primary)
    if meta is None:
        lines = [f"## Paper", f"(problem binds paper `{primary}` but "
                 f"Papers/{primary}/ is missing — tell the operator via "
                 f"feedback; proceed without it.)"]
    else:
        tpath = shelf.text_path(workspace, primary).as_posix()
        lines = [
            "## Paper",
            f"Source: `{meta.source_name}` (Papers/{primary}). The paper "
            f"is the authority for exact hypotheses/definitions — Read "
            f"`{tpath}` slices on demand (`## p.N` headings are page "
            f"anchors).",
        ]
        mpath = shelf.map_path(workspace, primary)
        try:
            body = mpath.read_text(encoding="utf-8").strip()
        except OSError:
            body = ""
        if body:
            if shelf.map_is_stale(workspace, primary):
                lines.append("(WARNING: the navigation map was built from "
                             "an older extraction — trust text.md over it.)")
            written = False
            if attempts_dir is not None:
                try:
                    (attempts_dir / PAPER_MAP_COMPANION).write_text(
                        body + "\n", encoding="utf-8")
                    written = True
                except OSError:
                    pass  # fall back to inline below
            if written:
                lines.append(
                    f"Navigation map (sections / dependencies / notation):"
                    f" `{PAPER_MAP_COMPANION}` (read-only companion) — Read"
                    f" or grep it before slicing the paper.")
            else:
                if len(body) > PAPER_INDEX_MAX_CHARS:
                    body = (body[:PAPER_INDEX_MAX_CHARS]
                            + "\n\n[TRUNCATED at Context cap — map.md "
                              "exceeds budget; the full map is on disk]")
                lines += ["", body]
        else:
            lines.append(f"(No navigation map — paper is short; read "
                         f"`{tpath}` directly.)")
    if aux:
        lines += ["", "### Auxiliary papers (Read/Grep on demand)"]
        for pid in aux:
            m = shelf.load_meta(workspace, pid)
            name = m.source_name if m else "?"
            has_map = shelf.map_path(workspace, pid).is_file()
            tail = (f"map at Papers/{pid}/map.md" if has_map
                    else f"short — read Papers/{pid}/text.md whole")
            lines.append(f"- `{name}` (Papers/{pid}): {tail}")
    return lines + [""]


def _section_presearch_candidates(problem_dir: Path, goal_id: int) -> list[str]:
    """target-1 pre-search: inject the cached per-node candidate-lemma
    section. Pure file-read of `.presearch/g<gid>.md` (written by
    `_presearch.ensure_presearch` during cold-prep, before this runs);
    returns [] when absent so the section appears only when pre-search
    produced verified candidates."""
    from ..pipeline import _presearch
    path = _presearch.presearch_path(problem_dir, goal_id)
    try:
        text = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
    except OSError:
        text = ""
    return [text, ""] if text else []


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
    the decision's argument into a `## The argument for this brick`
    section (resolving up the strategy chain when this spawn has no
    decision of its own).
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

    # Section ordering — cross-spawn-stable content (BRIEF + KB lessons)
    # leads so prompt-cache prefix-matching gets maximal hit: within one
    # Manifest version + KB state, the BRIEF + inline-lessons block is
    # byte-identical across all spawns of this problem. Putting them first
    # means the cache-able prefix length is the BRIEF + lessons size
    # (~2-10 KB) rather than zero. Per-goal / per-spawn surfaces follow.
    presearch_lines = _section_presearch_candidates(problem_dir, int(goal["id"]))
    section_names = [
        "brief", "kb_lessons", "paper_index", "programme", "directive",
        "inject_brief",
        "goal", "library_available", "strategy_naming", "parent_strategy",
        "mathlib_lemmas", "presearch", "proved_goals", "catalog",
        "prior_partial", "prior_patch", "goal_history",
    ]
    sections: list[list[str]] = [
        _section_brief_inline(problem_dir),
        _section_lessons_inline(conn, str(goal["problem"]), int(goal["id"]),
                                attempts_dir),
        # Paper navigation — cross-spawn-stable (map.md changes only on
        # regeneration), so it sits in the cacheable prefix with BRIEF.
        _section_paper_index(mfst, workspace, conn,
                             attempts_dir=attempts_dir),
        # Phase 2 — Strategist injections sit between cross-spawn-stable
        # content (BRIEF / LESSONS) and per-goal sections. Directive is
        # problem-level standing (every cold-start); brief is per-decision
        # one-shot (only when Strategist Inject spawned this pipeline).
        _section_programme_worker(conn, str(goal["problem"]),
                                  decision_id, problem_dir,
                                  goal_id=int(goal["id"])),
        _section_strategist_directive(conn, str(goal["problem"]),
                                      goal_id=int(goal["id"])),
        _section_strategist_brief(conn, decision_id, int(goal["id"])),
        _section_header(goal, workspace),
        _section_library_available(conn, mfst),
        _section_strategy_naming(strategy_id, goal),
        _section_parent_strategy(conn, goal, workspace),
        _section_mathlib_lemmas_from_deads(direct_events, workspace),
        # target-1 pre-search candidates (written in cold-prep). When present
        # it supersedes `_section_proved_goals` — both list this problem's
        # proved siblings, and the ranked pre-search list is the curated
        # surface (avoid the duplicate-section noise the design warns of).
        presearch_lines,
        ([] if presearch_lines
         else _section_proved_goals(conn, goal, workspace)),
        _section_catalog_pointer(conn, str(goal["problem"]), attempts_dir),
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
    write_context_stats(attempts_dir, label=f"{kind or 'goal'} g{goal['id']}",
                        names=section_names, sections=sections)

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
