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
# Outer entry — full agent integration
# ---------------------------------------------------------------------

def run_forward(conn: sqlite3.Connection, *, problem: str,
                workspace: Path, mfst: "Any", pipeline_id: str,
                decision_id: int | None = None) -> "Any":
    """Full Forward pipeline (Phase 2 §3.4).

    Stages:
      1. compile_forward_context  — Context.md with Strategist brief
      2. agent                    — spawn LLM, drops new_<slug>.lean
                                    or decline placeholder
      3. parse                    — extract_forward_metadata
                                    OR is_decline → forward_no_new_goal
      4. self_verify              — LSP verify_file on the candidate
      5. dedupe                   — find_canonicals_batch
      6. commit                   — commit_forward_lemma

    Returns `PipelineResult`:
      - outcome='proved' on sorry-free leaf-bypass commit
      - outcome='success' on regular sorry-stub commit (new goal in
        pool for BFS to attack)
      - outcome='failed', failure_reason='forward_no_new_goal' for
        decline / dedupe-blocked / parse-rejected paths
      - provider rc-based reasons on agent.spawn_llm rc != 0
    """
    from .. import agent
    from . import PipelineResult, PROMPT_DIR
    from ..agent.phase2_context import compile_forward_context

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, problem)

    # Stage 1 — Context.md
    compile_forward_context(
        conn, problem=problem, decision_id=decision_id,
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
    )

    # Stage 2 — agent spawn
    rc = agent.spawn_llm(
        kind="forward",
        prompt_path=PROMPT_DIR / "forward.md",
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
    )
    if rc != 0:
        return PipelineResult(
            outcome="failed",
            failure_reason=_rc_to_reason_fwd(rc),
            failure_detail=f"agent rc={rc}",
        )

    # Stage 3 — find the agent's output file. Glob for new_*.lean.
    candidates = list(attempts_dir.glob("new_*.lean"))
    if not candidates:
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail="agent produced no new_*.lean file",
        )
    src = candidates[0]
    try:
        body = src.read_text(encoding="utf-8")
    except OSError as e:
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=f"new_*.lean unreadable: {e}",
        )

    # Stage 3b — decline path
    if is_decline(body):
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail="agent declined: library_sufficient",
        )

    # Stage 4 — parse + self_verify metadata
    metadata, parse_err = extract_forward_metadata(body)
    if metadata is None:
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=f"parse rejected: {parse_err}",
        )

    # Stage 4b — LSP type-check the candidate. A sorry-bearing body
    # passes if and only if Lean elaborates the statement successfully
    # (sorry warning is OK). Sorry-free body must elaborate clean — no
    # errors. We re-use the existing /verify endpoint with
    # write_olean=False (probe-mode): no olean side effect, fast.
    from ..lsp import lifecycle as gateway_lifecycle
    try:
        v = gateway_lifecycle.verify_file(
            src, write_olean=False, workspace=workspace,
        )
    except Exception as e:
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=f"verify_file raised: {type(e).__name__}: {e}",
        )
    if not v.get("ok"):
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=f"lake elaborate failed: {v.get('error', v)}",
        )
    # Allow `sorry` warnings — they're expected for the statement-only
    # path. Reject other errors. The diagnostics filter is conservative
    # (only `severity==1` = "error" hits us; `severity==2` warnings
    # including sorry-warning are tolerated).
    err_diag = [
        d for d in (v.get("diagnostics") or [])
        if d.get("severity") == 1 and "sorry" not in str(d.get("message", "")).lower()
    ]
    if err_diag:
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=f"lake elaborate errors: {err_diag[:3]}",
        )

    # Stage 5 — dedupe. Forward proposals shouldn't clash with alive
    # canonicals (Strategist brief should have steered around them);
    # but the agent can still re-propose a near-duplicate. Phase 2
    # dedupe blocks `disproved` only; `shelved` doesn't block — so an
    # alias hit on an alive canonical means the agent's lemma is
    # redundant with the existing library.
    from ..quality import dedupe
    hits = dedupe.find_canonicals_batch(
        conn, workspace, problem=problem, parent_goal_id=0,
        candidates=[(metadata.slug, body)],
    )
    if hits and hits[0] is not None and hits[0].kind == "alias":
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=(
                f"dedupe blocked: alias to existing goal "
                f"{hits[0].goal_id}"
            ),
        )

    # Stage 6 — commit
    try:
        outcome = commit_forward_lemma(
            conn, problem=problem, workspace=workspace,
            attempts_dir=attempts_dir, metadata=metadata,
            source_filename=src.name,
        )
    except FileExistsError as e:
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=f"slug collision: {e}",
        )
    except Exception as e:
        return PipelineResult(
            outcome="failed", failure_reason="forward_no_new_goal",
            failure_detail=f"commit raised: {type(e).__name__}: {e}",
        )

    return PipelineResult(
        outcome="proved" if outcome.status == "proved" else "success",
        failure_reason="",
        failure_detail=(
            f"new forward goal {outcome.goal_id} at "
            f"{outcome.lean_path} (status={outcome.status})"
        ),
    )


def _rc_to_reason_fwd(rc: int) -> str:
    """Same rc taxonomy as Strategist (see strategist._rc_to_reason)."""
    if rc == 124:
        return "transient_timeout"
    if rc in (125, 128):
        return "spawn_fast_fail"
    if rc == 126:
        return "quota_exhausted"
    if rc == 127:
        return "missing_dep"
    return "spawn_fast_fail"
