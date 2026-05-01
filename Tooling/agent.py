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


def _section_naming_convention(strategy_id: int | None,
                               goal: sqlite3.Row) -> list[str]:
    if strategy_id is None:
        return []
    sid_token = f"s{strategy_id}"
    parent = goal["slug"]
    return [
        "## Naming convention (REQUIRED)",
        f"This Backward attempt has been allocated strategy id "
        f"`{sid_token}`. Multiple strategies may race for this goal in "
        f"parallel; collision-free naming is mandatory.",
        "",
        f"- Sub-goal slugs: `{sid_token}_sub_1`, "
        f"`{sid_token}_sub_2`, ... — exactly `{sid_token}_sub_<N>`.",
        f"- Sub-goal filenames: `new_{sid_token}_sub_<N>.lean`.",
        f"- Sub-goal theorem name = sub-goal slug.",
        f"- Patch filename: `patch_{parent}.lean` (parent slug, "
        f"no `{sid_token}` prefix).",
        f"- Patch theorem name: `{sid_token}` (NOT `{parent}` — "
        f"that name belongs to the parent's lean file and "
        f"would collide).",
        f"- Patch imports: `import Problems.<problem>.proofs."
        f"L_{sid_token}_sub_<N>` for each sub-goal.",
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


def _section_manifest_hints(mfst: manifest.Manifest) -> list[str]:
    if not mfst.mathlib_hints:
        return []
    return [
        "## Mathlib hints (from Manifest.md)",
        *(f"- {h}" for h in mfst.mathlib_hints),
        "",
    ]


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
    """F26 — Context.md gets a 1-line digest per attempt; full per-
    attempt content lives in PAST_ATTEMPTS.md (written separately by
    context_files.write_past_attempts)."""
    if not deads:
        return []
    out = ["## Previous attempts on THIS goal"]
    for i, d in enumerate(deads, 1):
        ago = _ago(d["ts"] if "ts" in d.keys() else None)
        digest = _digest_failure(d["failure_reason"],
                                 d["failure_detail"] or "")
        line = f"{i}. ({ago}) {d['failure_reason']}"
        if digest:
            line += f" — {digest}"
        out.append(line)
    out.append("")
    out.append(
        f"→ Full failure_detail + PROPOSAL.md per attempt: read "
        f"`{context_files.PAST_ATTEMPTS_FILENAME}` in this directory.")
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


def _section_lemma_references(deads: list[sqlite3.Row],
                              mfst: manifest.Manifest,
                              workspace: Path) -> list[str]:
    """F20 — `lake env lean #check` resolves real Mathlib signatures for
    names the agent has been confused about. Inject so weaker models
    don't have to guess arg order / instance shape from training memory."""
    names = _collect_lemma_names(deads, mfst)
    if not names:
        return []
    try:
        infos = lemma_lookup.lookup_batch(names, workspace)
    except Exception as exc:  # never block context generation
        print(f"[lemma_lookup] failed, skipping: {exc}", flush=True)
        return []
    bullets = [
        f"- **{info.name}** : `{info.signature}`"
        for info in infos.values() if info.found
    ]
    if not bullets:
        return []
    return [
        "## Lemma references (resolved from Mathlib)",
        "Ground-truth signatures for the lemmas Lean mentioned "
        "in past errors and the names the Manifest flagged. Use "
        "these to fix arg order / instance shape — do **not** "
        "improvise from memory when the signature is here.",
        "",
        *bullets,
        "",
    ]


def _fetch_strategy_dead_attempts(
    conn: sqlite3.Connection, goal_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT da.failure_reason, da.failure_detail, da.pipeline_id,"
        "       s.proposal_md AS strategy_proposal "
        "FROM dead_attempts da "
        "JOIN strategies s ON s.id = da.target_id "
        "WHERE da.target_kind = 'Strategy' AND s.goal_id = ? "
        "ORDER BY da.id DESC LIMIT 5",
        (goal_id,),
    ).fetchall()


def _section_past_verify_failures(rows: list[sqlite3.Row]) -> list[str]:
    """F26 — 1-line digest per past Verify failure; full content in
    PAST_VERIFIES.md (written separately by context_files.write_past_verifies)."""
    if not rows:
        return []
    out = [
        "## Past decompositions that failed Verify",
        "Earlier Backward attempts decomposed this goal but the "
        "combination patch did not elaborate against the sub-goal "
        "proofs. Avoid the same shape.",
        "",
    ]
    for i, d in enumerate(rows, 1):
        digest = _digest_failure(d["failure_reason"],
                                 d["failure_detail"] or "")
        line = (f"{i}. (pid {d['pipeline_id'][:12]}) "
                f"{d['failure_reason']}")
        if digest:
            line += f" — {digest}"
        out.append(line)
    out.append("")
    out.append(
        f"→ Full stderr + decomposition PROPOSAL.md per Verify failure: "
        f"read `{context_files.PAST_VERIFIES_FILENAME}` in this directory.")
    out.append("")
    return out


def compile_context(conn: sqlite3.Connection, *, goal: sqlite3.Row,
                    mfst: manifest.Manifest, attempts_dir: Path,
                    strategy_id: int | None = None) -> Path:
    """Write Context.md into attempts_dir. Pulls from DB + Manifest.

    `strategy_id`: when set (Backward worker), write a 'Naming convention'
    section instructing the agent to prefix all slugs with `s<sid>_`.
    Required for OR-parallel correctness — multiple Backwards on the same
    parent goal must produce non-colliding sub-goal slugs and theorem
    names.

    Section ordering — keep stable; agents may have learned to scan
    top-down. Each section function returns `[]` when not applicable
    so the resulting Context.md only contains sections with content.
    """
    workspace = attempts_dir.parent.parent  # .attempts/<pid> → workspace
    deads = db.recent_dead_attempts(
        conn, target_id=goal["id"], target_kind="Goal", k=5)
    strat_deads = _fetch_strategy_dead_attempts(conn, int(goal["id"]))

    sections: list[list[str]] = [
        _section_header(goal),
        _section_naming_convention(strategy_id, goal),
        _section_parent_strategy(conn, goal),
        _section_manifest_hints(mfst),
        # Lemma references is a precise expansion of mathlib_hints
        # (signatures resolved via lake env lean) — keep it adjacent
        # so the agent reads name + signature together rather than
        # scrolling past `## Strategic notes` to find the signatures.
        _section_lemma_references(deads, mfst, workspace),
        _section_manifest_forbidden(mfst),
        _section_manifest_notes(mfst),
        _section_playbook(goal, workspace),
        _section_past_attempts(deads),
        _section_past_verify_failures(strat_deads),
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

    Provider is resolved from `ASTERISM_LLM_PROVIDER` env (default:
    `claude`). Returns the provider's rc (0 success, 124 timeout,
    125 stale session (F33), 127 missing dep, other = error).

    `session_id` / `is_retry` / `retry_context`: F33 same-session
    Builder retry. Pass a UUID + is_retry=False on first attempt;
    same UUID + is_retry=True + the prior lake error string in
    `retry_context` on subsequent attempts.
    """
    return llm.get_provider().spawn(llm.LLMRequest(
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
