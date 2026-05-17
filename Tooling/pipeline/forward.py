"""Phase 2 — Forward pipeline (Step 6 scaffolding).

Forward produces a single new generic lemma per invocation. Strategist
brief (`strategist_decisions.brief` via queue.decision_id FK) directs
the research; Forward decides what specific statement to propose,
validates it type-checks, dedupes against alive/proved goals, and
commits the new theorem to `proofs/L_<slug>.lean`.

If the agent ships a sorry-free proof body, framework accepts it as a
proved leaf (Phase 2 leaf-bypass, mirror of Backward's behaviour).
Otherwise the new goal enters BFS with status='open' for later
Backward / Builder attack.

Stage order (docs/phase2/pipelines.md §3.4):
  1. failure_replay   (pure)   recent Forward output history
  2. compile_context  (pure)   Strategist brief + Library + Mathlib
                               candidates + TREE.md
  3. agent            (agent)  spawn LLM, get new_<slug>.lean ← TODO
  4. self_verify      (pure)   lake type-check (leading sorry OK)
  5. dedupe           (pure)   find_canonicals_batch
  6. commit           (pure)   move to proofs/L_<slug>.lean +
                               INSERT goal (kind=theorem, origin=forward,
                               entry_kind from leading comment)

Public surface (framework side; agent stage = TODO):
  - SLUG_RE                     — slug validation regex
  - extract_forward_metadata(text) -> ForwardMetadata | (None, err)
  - is_decline(text)            -> bool
  - commit_forward_lemma(...)    -> CommitOutcome
  - run_forward(...)            — outer entry (stub awaiting agent stage)
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..state import db


# Same slug constraint as Backward sub-goals (Tooling/pipeline/backward.py).
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SLUG_MAX_LEN = 60

# Leading-comment directives Forward agent writes:
#   `-- Forward rationale: <prose>`   required, 2-3 sentences
#   `-- entry_kind: Backward|Builder` required, routes new goal's first dispatch
#   `-- decline: library_sufficient`  agent decline (no lemma needed)
_RATIONALE_RE = re.compile(
    r"^\s*--\s*Forward\s+rationale\s*:\s*(.+?)$", re.MULTILINE | re.IGNORECASE,
)
_ENTRY_KIND_RE = re.compile(
    r"^\s*--\s*entry_kind\s*:\s*(Builder|Backward)\b",
    re.MULTILINE | re.IGNORECASE,
)
_DECLINE_RE = re.compile(
    r"^\s*--\s*decline\s*:\s*([a-z_]+)\b",
    re.MULTILINE | re.IGNORECASE,
)
# `theorem <slug> : <type> := by sorry` — captures slug.
_THEOREM_HEAD_RE = re.compile(
    r"^\s*theorem\s+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.MULTILINE,
)


# ---------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------

@dataclass
class ForwardMetadata:
    """Parsed leading-comment directives + theorem signature from a
    Forward agent's `new_<slug>.lean` output."""
    slug: str
    rationale: str
    entry_kind: str  # 'Builder' or 'Backward'
    sorry_free: bool  # True iff body has no `sorry` token


def extract_forward_metadata(text: str) -> tuple[ForwardMetadata | None, str]:
    """Parse a Forward agent's `new_<slug>.lean` file content.

    Returns (metadata, '') on success or (None, error_message) on a
    validation problem. Caller maps non-empty error to
    `failure_reason='forward_no_new_goal'` with the message as
    `failure_detail`.
    """
    thm_m = _THEOREM_HEAD_RE.search(text)
    if thm_m is None:
        return None, "no `theorem <slug> : <type>` declaration found"
    slug = thm_m.group(1)
    if not SLUG_RE.match(slug):
        return None, (
            f"slug {slug!r} must match {SLUG_RE.pattern} "
            f"(lowercase ASCII, digits, underscores)"
        )
    if len(slug) > SLUG_MAX_LEN:
        return None, f"slug {slug!r} exceeds max length {SLUG_MAX_LEN}"
    rat_m = _RATIONALE_RE.search(text)
    if rat_m is None:
        return None, "missing required `-- Forward rationale: ...` comment"
    rationale = rat_m.group(1).strip()
    if not rationale:
        return None, "Forward rationale comment is empty"
    ek_m = _ENTRY_KIND_RE.search(text)
    if ek_m is None:
        # Default 'Backward' per prompt spec.
        entry_kind = "Backward"
    else:
        entry_kind = ek_m.group(1)
        if entry_kind not in ("Builder", "Backward"):
            entry_kind = "Backward"
    # sorry detection — any `sorry` token below the imports.
    # Conservative: scan whole file; if `sorry` appears as a tactic /
    # term, treat the body as sorry-bearing. Lean does have `by sorry`
    # and term-mode `sorry`; both count.
    sorry_free = re.search(r"\bsorry\b", text) is None
    return ForwardMetadata(
        slug=slug, rationale=rationale, entry_kind=entry_kind,
        sorry_free=sorry_free,
    ), ""


def is_decline(text: str) -> bool:
    """True iff the file is a decline placeholder (e.g.
    `-- decline: library_sufficient` + trivial body). The framework
    surfaces this as `forward_no_new_goal` with detail 'agent declined'.
    """
    return _DECLINE_RE.search(text) is not None


# ---------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------

@dataclass
class CommitOutcome:
    """What commit_forward_lemma did."""
    goal_id: int
    lean_path: str
    status: str  # 'open' or 'proved' (sorry-free leaf-bypass)


def commit_forward_lemma(conn: sqlite3.Connection, *,
                         problem: str, workspace: Path,
                         attempts_dir: Path,
                         metadata: ForwardMetadata,
                         source_filename: str = "new_<slug>.lean",
                         ) -> CommitOutcome:
    """Move the validated `new_<slug>.lean` from attempts_dir into
    `proofs/L_<slug>.lean`, INSERT a goal row with origin='forward',
    and (if sorry-free) mark it `proved` for Phase 2 leaf-bypass.

    `source_filename`: filename in attempts_dir (typically
    `new_<slug>.lean`).

    No alias / dedupe handling here — caller's stage 5 (dedupe) is
    responsible for catching restatements before reaching commit.
    """
    src = attempts_dir / source_filename.replace("<slug>", metadata.slug)
    if not src.exists():
        # Fall back to any new_*.lean (agent may have used a different
        # name, e.g. slug auto-fix).
        candidates = list(attempts_dir.glob("new_*.lean"))
        if not candidates:
            raise FileNotFoundError(
                f"no new_*.lean in {attempts_dir} for forward commit"
            )
        src = candidates[0]
    body = src.read_text(encoding="utf-8")

    proofs_dir = db.problem_dir(workspace, problem) / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    dest = proofs_dir / f"L_{metadata.slug}.lean"
    if dest.exists():
        # Slug collision — extremely rare given the Forward agent uses
        # descriptive names + framework auto-suffix could be added in
        # future. For now, fail loudly so the operator sees it.
        raise FileExistsError(
            f"forward target {dest} already exists (slug collision)"
        )
    dest.write_text(body, encoding="utf-8")

    rel_lean_path = dest.relative_to(workspace).as_posix()
    # Pick statement string for goals.statement. Best-effort extract
    # the theorem type signature. Backward uses the same approach;
    # if extraction fails, store empty string (the lean_path is the
    # canonical artifact).
    statement = _extract_statement_string(body, metadata.slug) or ""

    initial_status = "proved" if metadata.sorry_free else "open"
    goal_id = db.insert_goal(
        conn, problem=problem, slug=metadata.slug,
        lean_path=rel_lean_path, statement=statement,
        origin="forward", depth=0, entry_kind=metadata.entry_kind,
    )
    if initial_status == "proved":
        db.update_goal_status(conn, goal_id, "proved")
    conn.commit()
    return CommitOutcome(goal_id=goal_id, lean_path=rel_lean_path,
                         status=initial_status)


def _extract_statement_string(body: str, slug: str) -> str | None:
    """Pull `theorem <slug> : <type>` substring up to `:=` or end of line.
    Best-effort; returns None if pattern doesn't match."""
    m = re.search(
        rf"theorem\s+{re.escape(slug)}\b\s*(.+?)(?::=|$)",
        body, re.DOTALL,
    )
    if m is None:
        return None
    s = m.group(1).strip()
    # Strip leading `:` (type signature starts after the colon)
    if s.startswith(":"):
        s = s[1:].strip()
    return s


# ---------------------------------------------------------------------
# Outer entry (stub — agent stage TODO)
# ---------------------------------------------------------------------

def run_forward(conn: sqlite3.Connection, *, problem: str,
                workspace: Path, pipeline_id: str,
                decision_id: int | None = None) -> "Any":
    """Outer entry — stages 1-2 (failure_replay + compile_context with
    Strategist brief) + 4-6 (self_verify lake check, dedupe, commit)
    are framework-side. Stage 3 (agent.spawn_llm dropping
    `new_<slug>.lean`) is the next-session piece.

    Real implementation will:
      1. compile_forward_context(conn, problem, decision_id, ...)
         writes Context.md with Strategist brief + Library state +
         Mathlib loogle candidates + past Forward history.
      2. agent.spawn_llm(prompt_path=PROMPT_DIR/forward.md, ...) drops
         either `new_<slug>.lean` or a decline file.
      3. is_decline(text) -> forward_no_new_goal/agent declined.
      4. extract_forward_metadata(text) -> validate + parse.
      5. mcp__lsp__validate_file(text) -> type-check (leading sorry OK).
      6. dedupe.find_canonicals_batch -> if any match alive/proved,
         skip + return forward_no_new_goal/dedupe blocked.
      7. commit_forward_lemma(...) -> proofs/L_<slug>.lean + INSERT.

    For now returns `failed/forward_unimplemented` matching the
    dispatcher's _run_pipeline placeholder branch.
    """
    from . import PipelineResult
    return PipelineResult(
        outcome="failed",
        failure_reason="forward_unimplemented",
        failure_detail=(
            "run_forward body (agent.spawn_llm + lean validation) "
            "is the next-session piece; framework-side commit logic "
            "(extract_forward_metadata / commit_forward_lemma) "
            "is implemented and unit-tested."
        ),
    )
