"""WorkArea + Context.md compilation + LLM dispatch.

LLM provider selection lives in `Tooling.llm` (see `llm/base.py`).
This module orchestrates: sandbox dir, Context.md generation from DB,
and forwarding to the configured provider.

Context.md is Asterism's A7 improvement over Hadamard: structured
failure_reason + full proposal_md from prior dead_attempts injected
into agent's sandbox.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import uuid
from pathlib import Path

from datetime import datetime, timezone

from . import context_files, db, lemma_lookup, llm, manifest, playbook


WORKER_TIMEOUT_SEC = 600  # 10 min, see architecture.md §13


class WorkArea:
    """Ephemeral working area for one pipeline run.

    Holds two paths under `.attempts/`:
      * `attempts` = `.attempts/<pid>/`         agent sandbox, Context.md, outputs
      * `backup`   = `.attempts/_backup_<pid>/` Backward's pre-write proofs/ snapshot

    Both are unconditionally rmtree'd on `__exit__` (best-effort). A worker
    that needs to consume `backup` (e.g. Backward restoring on lake fail)
    must `shutil.move` it before the context exits — `__exit__` only cleans
    whatever is still on disk.
    """
    def __init__(self, workspace: Path, pipeline_id: str):
        self.workspace = workspace
        self.pipeline_id = pipeline_id
        self.attempts = workspace / ".attempts" / pipeline_id
        self.backup = workspace / ".attempts" / f"_backup_{pipeline_id}"

    def __enter__(self) -> "WorkArea":
        self.attempts.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for p in (self.attempts, self.backup):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        return False


def _attempts_dir(workspace: Path, pipeline_id: str) -> Path:
    d = workspace / ".attempts" / pipeline_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------
# Context.md sections — each pure: `(...) -> list[str]` of lines (with
# trailing empty string for blank-line separator). Empty list means
# "section absent". `compile_context` orchestrates ordering + writes.
#
# Adding a new section is appending a function to the list in
# compile_context, no edits to the imperative blob.
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
        "  - `Context.md`, `PAST_ATTEMPTS.md`, `PAST_VERIFIES.md` "
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
    # Look up the parent goal + the strategy that produced this sub-goal
    # via strategy_subgoals → strategies → goals.
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
    # First emit raw manifest hints (preserving author phrasing),
    # but rewriting the lemma-name prefix when we have a signature.
    for hint in mfst.mathlib_hints:
        m = re.match(r"\s*([A-Z][\w']*(?:\.[\w']+)+)", hint)
        if m and m.group(1) in resolved:
            nm = m.group(1)
            out.append(f"- **{nm}** : `{resolved[nm]}`  ({hint[m.end():].strip().lstrip('-—').strip() or 'manifest hint'})")
            rendered.add(nm)
        else:
            out.append(f"- {hint}")
    # Then emit lookup-resolved names not already covered by a manifest hint
    # (these come from past lake errors — high-signal).
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

    # agent_no_response, forbidden_lemma, parse_proposal_fail,
    # naming_violation, goal_no_longer_open are all already short.
    if failure_reason != "lake_build_error":
        return failure_detail.strip().splitlines()[0][:160]

    # lake_build_error: walk lines to find the first real `error:` —
    # skipping the lake task-progress line (✖ [N/N] Building ...) and
    # any line that's clearly LEAN_PATH / lake-internal tracing.
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
    # Fallback: first non-trace line, capped
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


def _section_past_attempts(deads: list[sqlite3.Row]) -> list[str]:
    """F43 — full inline rendering of PAST_ATTEMPTS history into
    Context.md. Sonnet was previously trusted to Read PAST_ATTEMPTS.md
    on demand (compactness 2026-05-02 telemetry: ~58/59 sessions did,
    so the lazy mechanism worked here — but kept in Context for
    symmetry with PAST_VERIFIES, which Sonnet ignored 0/N times).

    Companion file is still written by `context_files.write_past_attempts`
    for forensics + future re-reading; this section duplicates its
    content so the agent can't miss it."""
    if not deads:
        return []
    out = ["## Previous attempts on THIS goal", ""]
    for i, d in enumerate(deads, 1):
        out.append(context_files._render_attempt_block(i, d).rstrip())
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
    # Manifest hints come as `Module.name` or `Module.name (Path:line)` —
    # the leading dotted token is the name we want.
    for hint in mfst.mathlib_hints:
        m = re.match(r"\s*([A-Z][\w']*(?:\.[\w']+)+)", hint)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            names.append(m.group(1))
    return names


# `_section_lemma_references` was merged into `_section_mathlib_lemmas`.


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
    (sub-goal cascade-shelve, F16 inward kill, etc). Each result includes
    the strategy's proposal_md plus the slug+statement of every sub-goal
    it spawned, so the next Backward can be told 'these decompositions
    were tried and failed — pick a different angle.'

    Filtered to strategies with a non-empty proposal_md AND at least one
    linked sub-goal — drops half-baked recovery cleanups (status='dead'
    + empty proposal) which carry no signal."""
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
    """F48 — Builder decline events on this goal. Each row's
    proposal_md carries the agent's reasoning for why direct proof
    isn't viable; Backward's Context.md surfaces this so the
    decomposition addresses the flagged hard parts instead of
    re-discovering them."""
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
    *what specifically* the Builder agent flagged as hard. Each entry
    is the prior PROPOSAL.md verbatim (already short — agent decline
    PROPOSALs are typically 3-10 lines)."""
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
    inferred from `mfst.lemma_hints` (any `Library.<Topic>.*` entries).
    Empty topic set → empty section (the agent isn't shown an unrelated
    Library tour).

    Each line is one previously-proved theorem from another Problem
    that the agent can now `import Library.<Topic>.<problem>` and use."""
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
        # Drop the `# Library/<Topic> — INDEX` heading; keep just the
        # bullet entries so the section reads cleanly inline.
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
    """F37 — anti-repetition hint for sequential Backward retry. Lists
    sub-goal decompositions from prior strategies on this goal that were
    cascade-killed (e.g. by a sub-goal hitting SHELVE_THRESHOLD). Helps
    the next Backward avoid re-proposing the same shape that already
    proved unreachable."""
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


def _section_past_verify_failures(rows: list[sqlite3.Row]) -> list[str]:
    """F43 — full inline rendering of PAST_VERIFIES history into
    Context.md. Compactness telemetry on 2026-05-02 showed Sonnet
    Read PAST_VERIFIES.md zero times across 59 sessions despite the
    prompt pointer; the resulting type-drift in re-Backward
    decompositions was the run's dominant time sink. Inline the full
    content so it lands in Sonnet's attention regardless.

    Companion file is still written for forensics."""
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
        out.append(context_files._render_strategy_block(i, r).rstrip())
        out.append("")
    return out


def compile_context(conn: sqlite3.Connection, *, goal: sqlite3.Row,
                    mfst: manifest.Manifest, attempts_dir: Path,
                    strategy_id: int | None = None,
                    kind: str | None = None) -> Path:
    """Write Context.md into attempts_dir. Pulls from DB + Manifest.

    `strategy_id`: when set (Backward worker), write a 'Naming convention'
    section instructing the agent to prefix all slugs with `s<sid>_`.
    Required because earlier strategies for the same goal may have left
    files on disk (cleanup is deferred to prune); each strategy must
    produce non-colliding sub-goal slugs and theorem names.

    `kind` (F43): 'builder' | 'backward' | None.
      - 'builder'  → render PAST_ATTEMPTS section, skip PAST_VERIFIES
      - 'backward' → render PAST_VERIFIES section, skip PAST_ATTEMPTS
      - None       → render both (back-compat for tests that don't
                     supply a kind; production callers always do)
    Each kind only sees the failure history it can actually act on:
    Builder fixes leaf-level patches, Backward fixes decomposition
    shape; cross-feeding adds noise without signal.

    Section ordering — keep stable; agents may have learned to scan
    top-down. Each section function returns `[]` when not applicable
    so the resulting Context.md only contains sections with content.
    """
    workspace = attempts_dir.parent.parent  # .attempts/<pid> → workspace
    deads = db.recent_dead_attempts(
        conn, target_id=goal["id"], target_kind="Goal", k=5)
    strat_deads = _fetch_strategy_dead_attempts(conn, int(goal["id"]))
    dead_strats = _fetch_dead_strategies(conn, int(goal["id"]))
    # F48 — Builder declines feed Backward only. Builder seeing its own
    # prior declines would tempt it to decline again without retrying.
    builder_declines = (
        _fetch_builder_declines(conn, int(goal["id"]))
        if kind == "backward" else []
    )

    show_attempts = kind in (None, "builder")
    show_verifies = kind in (None, "backward")

    # Dedupe: a strategy that died at Verify shows up in BOTH
    # `strat_deads` (with lake stderr + proposal) and `dead_strats`
    # (with proposal + sub-goals). Drop the strat-side entries from
    # `dead_strats` so the agent doesn't see the same proposal twice.
    # P0-#4: gate on `show_verifies`. For Builder kind we suppress
    # the verify-failures section, so applying the dedupe would silently
    # strip dead-strategy signal too.
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
        _section_past_attempts(deads) if show_attempts else [],
        _section_past_verify_failures(strat_deads) if show_verifies else [],
        _section_dead_strategies(dead_strats_filtered),
    ]

    parts: list[str] = []
    for section in sections:
        parts.extend(section)

    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")

    # F26 — write companion reference files for the bulky / lazy-load
    # content (Context.md only carries digests + pointers).
    context_files.write_past_attempts(deads, attempts_dir)
    context_files.write_past_verifies(strat_deads, attempts_dir)

    return out


def spawn_llm(*, kind: str, prompt_path: Path, problem_dir: Path,
              attempts_dir: Path,
              session_id: str | None = None,
              is_retry: bool = False,
              retry_context: str | None = None) -> int:
    """Dispatch to the configured LLM provider for one agent invocation.

    Provider is resolved per-kind (F39): `ASTERISM_<KIND>_PROVIDER` →
    `ASTERISM_LLM_PROVIDER` → 'claude'. Likewise the model string is
    looked up per-kind inside each provider. Returns the provider's
    rc (0 success, 124 timeout, 125 stale session (F33), 126 quota
    exhausted (F38 gemini), 127 missing dep, other = error).

    `session_id` / `is_retry` / `retry_context`: F33 same-session
    Builder retry. Pass a UUID + is_retry=False on first attempt;
    same UUID + is_retry=True + the prior lake error string in
    `retry_context` on subsequent attempts.
    """
    return llm.get_provider(kind=kind).spawn(llm.LLMRequest(
        kind=kind,
        prompt_path=prompt_path,
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
        timeout_sec=WORKER_TIMEOUT_SEC,
        session_id=session_id,
        is_retry=is_retry,
        retry_context=retry_context,
    ))


# Back-compat alias: existing code (and any external callers) referencing
# `agent.spawn_claude` still work. Will be removed in a future cleanup
# once all in-tree call sites are migrated.
spawn_claude = spawn_llm


def new_pipeline_id() -> str:
    return str(uuid.uuid4())


def attempts_dir_for(workspace: Path, pipeline_id: str) -> Path:
    return _attempts_dir(workspace, pipeline_id)
