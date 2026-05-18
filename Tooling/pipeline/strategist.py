"""Phase 2 — Strategist pipeline (Step 6 scaffolding).

Strategist emits a single meta-level decision per invocation:
  Inject / ConfirmShelve / Reopen / EmitDirective / InitializeDefs
  / RequestUserAmend / Noop

This module covers decision validation + commit; the agent stage
(actually spawning the LLM, writing `decision.json` to attempts_dir)
is the next-session piece. The framework-side logic — schema check,
Reopen ancestor safety walk, atomic side effects, strategist_decisions
audit row, last_strategist_at touch — is implemented in full.

Stage order (docs/phase2/pipelines.md §2.4):
  1. trigger_context  (pure)   compile input per trigger_kind
  2. failure_replay   (pure)   last 5 strategist_decisions
  3. agent            (agent)  spawn LLM, get decision.json  ← TODO
  4. self_verify      (pure)   schema + Reopen ancestor walk
  5. commit           (pure)   execute decision + audit row

Public surface:
  - DECISION_KINDS              — frozenset of valid `decision_kind`
  - parse_decision(json_text)    -> Decision | (None, error_msg)
  - verify_decision(decision, conn, problem) -> ok | error_msg
  - commit_decision(decision, conn, *, problem, tick, trigger_kind,
                    workspace, attempts_dir) -> Outcome
  - run_strategist(...)         — outer entry (stub awaiting agent stage)
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..state import db
from ..core import dispatcher as _dispatcher


# Decision kinds (mirrors strategist_decisions.decision_kind CHECK enum).
DECISION_KINDS: frozenset[str] = frozenset({
    "Inject", "ConfirmShelve", "Reopen", "EmitDirective",
    "InitializeDefs", "RequestUserAmend", "Noop",
})

# Trigger kinds (mirrors strategist_decisions.trigger_kind CHECK enum).
TRIGGER_KINDS: frozenset[str] = frozenset({
    "first_launch", "pending_review", "routine",
    "inject_batch_done",
})

# Files allowed in RequestUserAmend(file=...).
USER_AMEND_FILES: frozenset[str] = frozenset({"Defs.lean", "Manifest.md"})

# Built-in default cap on Inject(briefs=[...]) length. Each brief
# becomes its own Forward dispatch; a single Strategist invocation
# queuing many Forwards is almost certainly an agent error and would
# dominate the worker pool. N=1 (degenerate single-Forward case) is
# always allowed regardless of cap. Override via Asterism.yaml
# `strategist.inject_batch_max` or env `ASTERISM_INJECT_BATCH_MAX`;
# see `inject_batch_max()` resolver.
_INJECT_BATCH_MAX_DEFAULT: int = 10


def inject_batch_max() -> int:
    """Resolve the Inject batch upper bound through the standard
    config chain (env → Asterism.yaml → built-in default). Read at
    verify-time so tuning doesn't require a daemon restart."""
    from ..core import config
    return int(config.get(
        "strategist.inject_batch_max",
        default=_INJECT_BATCH_MAX_DEFAULT,
        env_var="ASTERISM_INJECT_BATCH_MAX",
        cast=int,
    ))


# ---------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------

@dataclass
class Decision:
    """Parsed Strategist decision. Mirrors `docs/phase2/pipelines.md`
    §2.3 schema. `brief` and `reason` are mutually-orthogonal (per
    decision kind) text fields; `payload` holds structured params
    (pipeline name / file / lean_body / question / scope / body /
    directive) keyed by decision kind."""
    kind: str
    target_id: int | None = None
    brief: str | None = None
    reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------

def parse_decision(json_text: str) -> tuple[Decision | None, str]:
    """Parse the agent's `decision.json` content. Returns
    (Decision, '') on success or (None, error_message) on failure.

    Accepts both the canonical shape (`kind` + flat fields) and a
    forgiving variant where structured params can live either at top
    level or inside a `payload` sub-dict.
    """
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"not valid JSON: {e}"
    if not isinstance(obj, dict):
        return None, "decision must be a JSON object (got list/scalar)"
    kind = obj.get("kind")
    if not isinstance(kind, str) or kind not in DECISION_KINDS:
        return None, (
            f"missing or unknown 'kind' ({kind!r}); expected one of "
            f"{sorted(DECISION_KINDS)}"
        )
    target_id = obj.get("target_goal_id") or obj.get("target_id")
    if target_id is not None:
        try:
            target_id = int(target_id)
        except (TypeError, ValueError):
            return None, f"target_id must be int or null (got {target_id!r})"
    brief = obj.get("brief")
    reason = obj.get("reason")
    # Pull all structured params (anything not already consumed) into
    # payload. Lets agent send either nested-payload or flat shape.
    payload_inner = obj.get("payload")
    if isinstance(payload_inner, dict):
        payload = dict(payload_inner)
    else:
        payload = {}
    for k, v in obj.items():
        if k in ("kind", "target_goal_id", "target_id",
                 "brief", "reason", "payload"):
            continue
        payload[k] = v
    return Decision(kind=kind, target_id=target_id, brief=brief,
                    reason=reason, payload=payload), ""


# ---------------------------------------------------------------------
# Schema validation (self_verify stage)
# ---------------------------------------------------------------------

def verify_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str) -> str:
    """Validate decision shape + cross-row constraints. Returns '' if
    OK, an error message string otherwise.

    Checks:
      - Required fields per decision kind
      - target_id exists in goals (when set)
      - Inject.pipeline is currently restricted to 'Forward'
      - Reopen ancestor safety walk (no `disproved` ancestor)
      - RequestUserAmend file ∈ {Defs.lean, Manifest.md}
      - RequestUserAmend dedup: no other awaiting_human row for this problem
    """
    k = decision.kind

    if k == "Inject":
        pipeline = decision.payload.get("pipeline")
        if pipeline != "Forward":
            return (f"Inject.pipeline must be 'Forward' "
                    f"(got {pipeline!r}); Phase 2 only supports Forward")
        # Phase 2.5 (unified) — Inject carries `briefs: list[str]`. N=1
        # is the degenerate case (single Forward); N>1 is a parallel
        # batch. Every commit creates a batch_id + N audit rows + N
        # Forward enqueues; cascade fires one Strategist
        # `inject_batch_done` trigger when the last sibling finishes.
        briefs = decision.payload.get("briefs")
        if briefs is None:
            return ("Inject requires `briefs: list[str]` "
                    "(use a 1-element list for a single Forward)")
        if not isinstance(briefs, list):
            return (f"Inject.briefs must be a list "
                    f"(got {type(briefs).__name__})")
        if len(briefs) < 1:
            return "Inject.briefs must contain >= 1 brief"
        cap = inject_batch_max()
        if len(briefs) > cap:
            return (f"Inject.briefs too large "
                    f"(got {len(briefs)}, max {cap})")
        for i, b in enumerate(briefs):
            if not isinstance(b, str) or not b.strip():
                return (f"Inject.briefs[{i}] must be a non-empty string")
        if decision.brief and str(decision.brief).strip():
            return ("Inject schema dropped the legacy `brief` field; "
                    "wrap your single brief in a 1-element `briefs` list")
        return ""

    if k == "Noop":
        if not decision.reason or not str(decision.reason).strip():
            return "Noop requires non-empty reason"
        return ""

    if k == "EmitDirective":
        scope = decision.payload.get("scope")
        body = decision.payload.get("body")
        if not isinstance(scope, str) or not scope.startswith("problem:"):
            return f"EmitDirective.scope must be 'problem:<name>' (got {scope!r})"
        if not isinstance(body, str) or not body.strip():
            return "EmitDirective requires non-empty body"
        return ""

    if k == "ConfirmShelve":
        if decision.target_id is None:
            return "ConfirmShelve requires target_goal_id"
        g = db.get_goal(conn, decision.target_id)
        if g is None:
            return f"target_goal_id={decision.target_id} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem {g['problem']!r}, "
                    f"not this Strategist's {problem!r}")
        if not decision.reason or not str(decision.reason).strip():
            return "ConfirmShelve requires non-empty reason"
        return ""

    if k == "Reopen":
        if decision.target_id is None:
            return "Reopen requires target_goal_id"
        g = db.get_goal(conn, decision.target_id)
        if g is None:
            return f"target_goal_id={decision.target_id} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem {g['problem']!r}, "
                    f"not this Strategist's {problem!r}")
        # Phase 2 Rule 3 safety walk
        if _dispatcher._has_terminal_disproved_ancestor(
            conn, decision.target_id
        ):
            return (
                f"Reopen rejected: goal {decision.target_id} has a "
                f"'disproved' ancestor (counterexample already shown). "
                f"Use ConfirmShelve."
            )
        if not decision.reason or not str(decision.reason).strip():
            return "Reopen requires non-empty reason"
        return ""

    if k == "InitializeDefs":
        if decision.payload.get("problem") and \
                decision.payload["problem"] != problem:
            return (f"InitializeDefs.problem mismatch: payload says "
                    f"{decision.payload['problem']!r}, expected {problem!r}")
        lean_body = decision.payload.get("lean_body")
        if not isinstance(lean_body, str) or not lean_body.strip():
            return "InitializeDefs requires non-empty lean_body"
        # File-existence guard (only-when-missing). Caller (commit) re-
        # checks atomically; this is the friendlier early reject.
        # `commit_decision` resolves workspace; verify_decision doesn't
        # have workspace, so skip the existence check here.
        return ""

    if k == "RequestUserAmend":
        if decision.payload.get("problem") and \
                decision.payload["problem"] != problem:
            return (f"RequestUserAmend.problem mismatch: payload says "
                    f"{decision.payload['problem']!r}, expected {problem!r}")
        file = decision.payload.get("file")
        if file not in USER_AMEND_FILES:
            return (f"RequestUserAmend.file must be one of "
                    f"{sorted(USER_AMEND_FILES)} (got {file!r})")
        proposed_body = decision.payload.get("proposed_body")
        if not isinstance(proposed_body, str) or not proposed_body.strip():
            return "RequestUserAmend requires non-empty proposed_body"
        question = decision.payload.get("question")
        if not isinstance(question, str) or not question.strip():
            return "RequestUserAmend requires non-empty question"
        # Phase 2 §2.5 — one awaiting_human row per problem at a time
        if db.problem_has_awaiting_human(conn, problem):
            return (
                f"RequestUserAmend rejected: problem {problem!r} already "
                f"has an outstanding awaiting_human strategist_decisions "
                f"row; resolve it before issuing another."
            )
        return ""

    return f"verify_decision: unhandled kind {k!r}"


# ---------------------------------------------------------------------
# Commit (side-effect stage)
# ---------------------------------------------------------------------

@dataclass
class CommitOutcome:
    """What commit_decision did — for the caller (run_strategist) to
    record into the pipeline's PipelineResult and dead_attempt rows.

    `decision_row_id`: id of the FIRST inserted strategist_decisions
      row in the batch (for callers that need a single canonical id).
      Full row id list in `batch_decision_row_ids`.
    `enqueued_forward`: True iff the commit emitted >= 1 Inject(Forward)
      queue entry.
    `batch_id`: always non-None when the committed decision was Inject
      (every Inject — including N=1 — is a batch under the unified
      Phase 2.5 schema); None for non-Inject decision kinds.
    `batch_decision_row_ids`: row ids in `briefs` list order (length N
      for Inject; empty for non-Inject kinds).
    `final_outcome`: 'committed' (decision applied) / 'awaiting_human'
      (RequestUserAmend wrote .proposed_<file> + INSERT row, dispatcher
      blocks problem until operator resolves) / 'noop'.
    """
    decision_row_id: int
    enqueued_forward: bool = False
    final_outcome: str = "committed"
    batch_id: str | None = None
    batch_decision_row_ids: list[int] = field(default_factory=list)


def _commit_inject_batch(decision: Decision, conn: sqlite3.Connection,
                         *, problem: str, tick: int,
                         trigger_kind: str) -> CommitOutcome:
    """Atomically commit one Strategist Inject(briefs=[...]) decision
    as N audit rows + N Forward enqueues sharing a single batch_id.
    Wraps every side effect into one transaction so a mid-commit
    failure leaves no orphan rows / enqueues.

    N=1 is the degenerate single-Forward case under the unified Phase 2.5
    schema; the batch infrastructure (batch_id, step_index payload,
    cascade-side `_maybe_enqueue_inject_batch_done` hook) handles it
    uniformly with N>=2.
    """
    briefs: list[str] = list(decision.payload["briefs"])
    batch_id = uuid.uuid4().hex
    ts = db.now()
    row_ids: list[int] = []
    for i, brief in enumerate(briefs):
        row_payload = {
            "pipeline": "Forward",
            "step_index": i,
            "batch_size": len(briefs),
        }
        cur = conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, target_id, brief, reason, payload,"
            " batch_id, outcome, created_at, updated_at)"
            " VALUES (?, ?, ?, 'Inject', NULL, ?, ?, ?, ?, NULL, ?, ?)",
            (problem, tick, trigger_kind, brief.strip(),
             decision.reason, json.dumps(row_payload, ensure_ascii=False),
             batch_id, ts, ts),
        )
        row_ids.append(int(cur.lastrowid))
    for rid in row_ids:
        db.enqueue(
            conn, kind="Forward", target_id=problem,
            target_kind="Problem", priority=10,
            decision_id=rid,
        )
    db.update_problem_last_strategist_at(conn, problem)
    db.set_problem_bootstrap_done(conn, problem)
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_ids[0],
        enqueued_forward=True,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=row_ids,
    )


def commit_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str, tick: int, trigger_kind: str,
                    workspace: Path) -> CommitOutcome:
    """Execute decision side effects + INSERT audit row.

    Caller must have already passed `verify_decision`. This is the
    write-path; errors here indicate a bug (or a race with another
    Strategist commit), not user error.
    """
    # Resolve root id for enqueues.
    root_id_row = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()
    root_id = int(root_id_row["id"]) if root_id_row else None

    k = decision.kind
    outcome = "committed"
    enqueued_forward = False

    # Phase 2.5 unified — every Inject is a batch (N=1 is degenerate).
    # Emits N audit rows + N Forward enqueues under one batch_id;
    # cascade fires Strategist with trigger_kind='inject_batch_done'
    # when the last Forward finishes (see
    # dispatcher._maybe_enqueue_inject_batch_done). Routes through the
    # batch helper unconditionally — the legacy solo path that wrote
    # a single batch_id-less row was removed.
    if k == "Inject":
        return _commit_inject_batch(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind,
        )

    if k == "Noop":
        # No side effect beyond the audit row + last_strategist_at.
        pass

    elif k == "EmitDirective":
        db.set_problem_strategist_directive(
            conn, problem, str(decision.payload.get("body", "")).strip()
        )

    elif k == "InitializeDefs":
        defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
        if defs_path.exists():
            raise RuntimeError(
                f"InitializeDefs would overwrite existing {defs_path}; "
                "verify_decision should have caught this"
            )
        defs_path.write_text(decision.payload["lean_body"],
                             encoding="utf-8")

    elif k == "ConfirmShelve":
        gid = int(decision.target_id)  # type: ignore[arg-type]
        db.update_goal_status(conn, gid, "shelved")
        _dispatcher._propagate_shelve(conn, gid)
        _dispatcher._cascade_shelve_descendants(conn, gid)

    elif k == "Reopen":
        gid = int(decision.target_id)  # type: ignore[arg-type]
        # Status must be 'open' (not 'attempting'): `db.open_goals` is
        # the BFS dispatch source and filters `status = 'open'`. Setting
        # 'attempting' without enqueueing leaves the goal invisible to
        # bfs_refill → daemon idle-exits on a Reopen'd root. Symmetric
        # with `_propagate_shelve` reopen branch (line 307) and verify
        # rollback culprit branch (verify.py:263).
        db.update_goal_status(conn, gid, "open")
        # Auto-detach: if upward strategy chain is broken, set
        # goals.detached so BFS still dispatches.
        if _dispatcher._has_dead_strategy_in_chain(conn, gid):
            db.set_goal_detached(conn, gid, True)
        # Optional directive: write to problems.strategist_directive
        directive = decision.payload.get("directive")
        if isinstance(directive, str) and directive.strip():
            db.set_problem_strategist_directive(
                conn, problem, directive.strip())

    elif k == "RequestUserAmend":
        # Atomic three-step: tmp write -> INSERT row -> rename
        # (see docs/phase2/pipelines.md §2.5).
        file = decision.payload["file"]
        target_path = db.problem_dir(workspace, problem) / f".proposed_{file}"
        body = str(decision.payload["proposed_body"])
        # Step 1: write to a temp file in the same directory then fsync.
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".proposed_{file}.", dir=str(target_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
                fh.flush()
                os.fsync(fh.fileno())
            # Step 2: INSERT audit row with outcome='awaiting_human'.
            # Step 3 (rename) happens below after the row is in place.
            # Stuffed into the row INSERT path below for atomicity.
        except Exception:
            # Best-effort cleanup of orphan tmp
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        # Stash for the post-INSERT rename below
        decision.payload["__tmp_path__"] = tmp_name
        decision.payload["__final_path__"] = str(target_path)
        outcome = "awaiting_human"

    else:
        raise RuntimeError(f"commit_decision: unhandled kind {k!r}")

    # INSERT audit row. brief and reason live in dedicated columns;
    # other structured params go in payload JSON (excluding the tmp
    # path bookkeeping for RequestUserAmend).
    payload_for_audit = {
        k: v for k, v in decision.payload.items()
        if not str(k).startswith("__")
    }
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (problem, tick, trigger_kind, decision.kind,
         decision.target_id, decision.brief, decision.reason,
         json.dumps(payload_for_audit, ensure_ascii=False),
         outcome if outcome != "committed" else None,
         ts, ts),
    )
    decision_row_id = int(cur.lastrowid)

    # Post-INSERT side effects requiring the row id. Inject is handled
    # earlier via _commit_inject_batch (returns early); only
    # RequestUserAmend's atomic rename lives here.
    if k == "RequestUserAmend":
        # Atomic rename: temp -> .proposed_<file>. If this fails the
        # audit row is rolled back via the outer transaction.
        os.rename(decision.payload["__tmp_path__"],
                  decision.payload["__final_path__"])

    # Touch last_strategist_at; bootstrap_done=1 on every commit (any
    # decision kind closes the T0 first-launch window).
    db.update_problem_last_strategist_at(conn, problem)
    db.set_problem_bootstrap_done(conn, problem)
    conn.commit()

    return CommitOutcome(
        decision_row_id=decision_row_id,
        enqueued_forward=enqueued_forward,
        final_outcome=outcome,
    )


# ---------------------------------------------------------------------
# Outer entry — full agent integration
# ---------------------------------------------------------------------

def run_strategist(conn: sqlite3.Connection, *, problem: str,
                   trigger_kind: str, tick: int,
                   workspace: Path,
                   mfst: "Any",
                   pipeline_id: str,
                   pending_review_id: int | None = None) -> "Any":
    """Full Strategist pipeline (Phase 2 §2.4).

    Stages:
      1. trigger_context   — compile Strategist-flavoured Context.md
      2. agent             — spawn LLM, drops `decision.json` in
                             attempts_dir
      3. self_verify       — parse + verify_decision
      4. commit            — commit_decision side effects
      5. status mapping    — Noop / schema invalid → infra-reason
                             (no attempts++); commit → success

    Returns `PipelineResult` with one of:
      - outcome='success' on a clean commit (any decision kind)
      - outcome='failed', failure_reason='strategist_noop' on Noop
        (treated as infra so cascade_one doesn't burn root.attempts)
      - outcome='failed', failure_reason='strategist_schema_invalid'
        when parse/verify rejects the agent's output
      - outcome='failed', failure_reason='agent_no_output' if no
        decision.json produced
      - provider rc-based reasons (quota / spawn_fast_fail / ...) on
        agent.spawn_llm rc != 0
    """
    from .. import agent
    from . import PipelineResult, PROMPT_DIR
    from ..agent.phase2_context import compile_strategist_context

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, problem)

    # Stage 1 — Context.md
    compile_strategist_context(
        conn, problem=problem, trigger_kind=trigger_kind,
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=pending_review_id,
    )

    # Stage 2 — agent spawn
    rc = agent.spawn_llm(
        kind="strategist",
        prompt_path=PROMPT_DIR / "strategist.md",
        problem_dir=problem_dir,
        attempts_dir=attempts_dir,
    )
    if rc != 0:
        return PipelineResult(
            outcome="failed",
            failure_reason=_rc_to_reason(rc),
            failure_detail=f"agent rc={rc}",
        )

    # Stage 3 — parse decision.json
    decision_path = attempts_dir / "decision.json"
    if not decision_path.exists():
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail="decision.json not produced",
        )
    try:
        decision_text = decision_path.read_text(encoding="utf-8")
    except OSError as e:
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail=f"decision.json unreadable: {e}",
        )
    decision, parse_err = parse_decision(decision_text)
    if decision is None:
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"parse: {parse_err}",
        )

    # Stage 4 — self_verify
    verify_err = verify_decision(decision, conn, problem=problem)
    if verify_err:
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"verify: {verify_err}",
        )

    # Stage 5 — commit + outcome mapping
    if decision.kind == "Noop":
        # Even Noop touches last_strategist_at + bootstrap_done via
        # commit_decision; it's a real commit (audit row), just no
        # cascade-visible effect. Map to infra-reason so cascade_one
        # doesn't try to attempts++ on the root.
        commit_decision(decision, conn, problem=problem, tick=tick,
                        trigger_kind=trigger_kind, workspace=workspace)
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_noop",
            failure_detail=str(decision.reason or ""),
        )

    try:
        outcome = commit_decision(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, workspace=workspace,
        )
    except Exception as e:
        # Commit must succeed once verify passed; any error here is
        # a framework bug. Surface as schema_invalid so dispatcher
        # doesn't burn root.attempts on a framework-side issue.
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"commit raised: {type(e).__name__}: {e}",
        )

    return PipelineResult(
        outcome="success",
        failure_reason="",
        failure_detail=(
            f"committed {decision.kind}"
            + (f" (decision_row={outcome.decision_row_id}, "
               f"forward_enqueued={outcome.enqueued_forward}, "
               f"final_outcome={outcome.final_outcome})")
        ),
    )


def _rc_to_reason(rc: int) -> str:
    """Map agent.spawn_llm rc to failure_reason for Strategist / Forward.
    Mirrors backward.py / builder.py rc handling but consolidated here
    so the new pipelines share the same channel-failure taxonomy."""
    if rc == 124:
        return "transient_timeout"
    if rc == 125:
        return "spawn_fast_fail"
    if rc == 126:
        return "quota_exhausted"
    if rc == 127:
        return "missing_dep"
    if rc == 128:
        return "spawn_fast_fail"  # stuck thinking — treat as infra
    return "spawn_fast_fail"
