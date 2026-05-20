"""Phase 2 — Strategist pipeline (Step 6 scaffolding).

Strategist emits a single meta-level decision per invocation:
  Inject / ConfirmShelve / Reopen / EmitDirective
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
    "RequestUserAmend", "Noop",
})

# Trigger kinds (mirrors strategist_decisions.trigger_kind CHECK enum).
TRIGGER_KINDS: frozenset[str] = frozenset({
    "first_launch", "pending_review", "routine",
    "inject_batch_done",
})

# Files allowed in RequestUserAmend(file=...).
USER_AMEND_FILES: frozenset[str] = frozenset({"Defs.lean", "Manifest.md"})

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

def parse_decisions(json_text: str) -> tuple[list[Decision] | None, str]:
    """Parse the agent's `decision.json` content into a list of decisions.

    Multi-decision schema: top-level is a JSON array of one or more
    decision objects. Single-decision back-compat: a top-level dict is
    accepted and wrapped as `[dict]` so agents that still emit one
    object work unchanged. Returns (decisions, '') on success or
    (None, error_message) on any malformed item.
    """
    try:
        obj = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as e:
        return None, f"not valid JSON: {e}"
    if isinstance(obj, dict):
        items = [obj]
    elif isinstance(obj, list):
        if not obj:
            return None, "decision array is empty; emit at least one decision"
        items = obj
    else:
        return None, (
            "decision.json must be a JSON object or array of objects "
            f"(got {type(obj).__name__})"
        )
    out: list[Decision] = []
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            return None, (
                f"decision #{i} must be a JSON object (got "
                f"{type(raw).__name__})"
            )
        d, err = _parse_one(raw)
        if d is None:
            return None, (f"decision #{i}: {err}" if len(items) > 1 else err)
        out.append(d)
    return out, ""


def parse_decision(json_text: str) -> tuple[Decision | None, str]:
    """Single-decision wrapper around `parse_decisions`. Returns the
    sole Decision when the payload contains exactly one; errors when
    it parses cleanly but contains multiple. Existing call sites that
    only handle one decision at a time go through here; the agent
    runner (`run_strategist`) calls `parse_decisions` directly.
    """
    decisions, err = parse_decisions(json_text)
    if decisions is None:
        return None, err
    if len(decisions) != 1:
        return None, (
            f"expected a single decision; got {len(decisions)}. Use "
            f"parse_decisions for multi-decision batches."
        )
    return decisions[0], ""


def _parse_one(obj: dict[str, Any]) -> tuple[Decision | None, str]:
    """Parse a single decision-object into a `Decision`. Shared by both
    the single-decision and multi-decision parsers.

    Accepts both the canonical shape (`kind` + flat fields) and a
    forgiving variant where structured params can live either at top
    level or inside a `payload` sub-dict.
    """
    kind = obj.get("kind")
    if not isinstance(kind, str) or kind not in DECISION_KINDS:
        return None, (
            f"missing or unknown 'kind' ({kind!r}); expected one of "
            f"{sorted(DECISION_KINDS)}"
        )
    # target_id accepts int (goal_id) or str (slug). Slug → int lookup
    # happens in verify_decision (it has `problem` context). Integer
    # strings (e.g. "2019") are coerced here so callers don't need to
    # special-case them.
    target_id = obj.get("target_goal_id") or obj.get("target_id")
    if target_id is not None and not isinstance(target_id, int):
        if isinstance(target_id, str):
            try:
                target_id = int(target_id)
            except ValueError:
                pass  # leave as str; verify_decision will lookup by slug
        else:
            return None, (f"target_id must be int, slug string, or null "
                          f"(got {type(target_id).__name__})")
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

    Side effect: when `decision.target_id` is a slug string (e.g. agent
    emitted `target_goal_id="main"`), looks up the corresponding goal_id
    by (problem, slug) and rewrites `decision.target_id` to the int.
    Unknown slug → error. Keeps the agent-facing schema forgiving
    without leaking string IDs into commit_decision's int-typed paths.
    """
    k = decision.kind

    # Slug → int normalization for kinds that carry target_id.
    if isinstance(decision.target_id, str):
        row = conn.execute(
            "SELECT id FROM goals WHERE problem = ? AND slug = ?",
            (problem, decision.target_id),
        ).fetchone()
        if row is None:
            return (f"target_id={decision.target_id!r} (slug) not found "
                    f"in problem {problem!r}; use the integer goal id "
                    f"shown in Context.md's active goal list")
        decision.target_id = int(row["id"])

    if k == "Inject":
        pipeline = decision.payload.get("pipeline")
        if pipeline not in ("Forward", "Backward", "Builder"):
            return (f"Inject.pipeline must be one of "
                    f"'Forward'/'Backward'/'Builder' (got {pipeline!r})")
        # Phase 6 unified — one Inject = one decision = one pipeline
        # dispatch. `brief` is the agent-facing text payload across all
        # three variants:
        #   - Forward: lemma description (what to produce on a new goal)
        #   - Backward / Builder: directive (how to redispatch on an
        #     existing goal — "try this angle"). Used for the change-
        #     direction workflow on pending_review.
        # Multi-Inject in one Strategist call lands later via the
        # multi-decision schema, where each Inject is its own decision.
        if not isinstance(decision.brief, str) or not decision.brief.strip():
            return f"Inject({pipeline}) requires non-empty `brief` (string)"
        if decision.payload.get("briefs") or decision.payload.get("directive"):
            return (f"Inject schema uses top-level `brief: str`; "
                    f"`briefs` / `directive` payload fields are legacy "
                    f"— remove them and put your text in `brief`")
        if pipeline == "Forward":
            if decision.target_id is not None:
                return ("Inject(Forward) targets the problem (no goal yet "
                        "produced); `target_goal_id` must be null. Use "
                        "Inject(Backward, target_goal_id=...) for "
                        "redispatch on an existing goal.")
            return ""
        # Backward / Builder
        target = decision.target_id
        if target is None:
            return (f"Inject({pipeline}) requires `target_goal_id` "
                    f"(integer id or slug shown in Context.md's "
                    f"active goal list)")
        g = db.get_goal(conn, int(target))
        if g is None:
            return f"target_goal_id={target} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem "
                    f"{g['problem']!r}, not {problem!r}")
        if str(g["status"]) in ("proved", "disproved", "dead"):
            return (f"target_goal_id={target} is {g['status']!r}; "
                    f"Inject({pipeline}) cannot redispatch a terminal "
                    f"goal. proved/disproved/dead are hard terminals; "
                    f"open a different angle on a different goal instead.")
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
        # Phase 6 safety walk — block Reopen if any ancestor is
        # `disproved` (counterexample) or `dead` (parent strategy was
        # wrong, descendant moot in that context). `shelved` ancestor
        # is OK — auto-detach in commit lets the goal run standalone.
        bad, kind = _dispatcher._has_hard_terminal_ancestor(
            conn, decision.target_id
        )
        if bad:
            if kind == "disproved":
                return (
                    f"Reopen rejected: goal {decision.target_id} has a "
                    f"'disproved' ancestor (counterexample already shown). "
                    f"Use ConfirmShelve."
                )
            return (
                f"Reopen rejected: goal {decision.target_id} has a "
                f"'dead' ancestor (parent strategy was wrong; this "
                f"descendant exists only in that abandoned context). "
                f"Inject(Backward, target=<parent-goal>) to try a "
                f"different decomposition instead."
            )
        if not decision.reason or not str(decision.reason).strip():
            return "Reopen requires non-empty reason"
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


def verify_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str) -> str:
    """Validate a multi-decision batch. Runs `verify_decision` on each
    item in declared order, then applies cross-decision invariants that
    only matter when multiple decisions land in the same call.

    Cross-decision rules:
      - At most one `RequestUserAmend` per batch (the per-item check
        already forbids a second awaiting_human row, but two amends in
        the SAME batch both see an empty awaiting_human row at verify
        time and would both pass; this explicit check catches it).
      - No `(ConfirmShelve(G), Reopen(G))` pair on the same target
        within one batch — contradictory intent, almost certainly an
        agent error. Order independent: either ordering is rejected.

    Returns '' if all pass, an error message otherwise (first failure
    short-circuits). Caller must abort the commit when this returns
    non-empty — `commit_decisions` assumes verify passed.
    """
    for i, d in enumerate(decisions):
        err = verify_decision(d, conn, problem=problem)
        if err:
            return (f"decision #{i}: {err}" if len(decisions) > 1 else err)

    # Cross-decision: no ConfirmShelve(G) + Reopen(G) pair.
    confirm_targets: set[int] = {
        int(d.target_id) for d in decisions
        if d.kind == "ConfirmShelve" and d.target_id is not None
    }
    reopen_targets: set[int] = {
        int(d.target_id) for d in decisions
        if d.kind == "Reopen" and d.target_id is not None
    }
    overlap = confirm_targets & reopen_targets
    if overlap:
        gid = next(iter(overlap))
        return (
            f"batch contains both ConfirmShelve and Reopen for goal "
            f"{gid} — contradictory. Pick one."
        )

    # Cross-decision: no ConfirmShelve(G) + Inject(Backward/Builder,
    # target=G) pair. The Inject force-reopens G (shelved /
    # pending_strategist_review / frozen → open in
    # `_commit_inject_redispatch`) and queues a retry; the
    # ConfirmShelve then flips G back to shelved. End state: G is
    # shelved but a Backward/Builder dispatch sits in the queue
    # targeting it. BFS would then try to dispatch a worker on a
    # shelved goal — undefined behaviour.
    inject_bb_targets: set[int] = {
        int(d.target_id) for d in decisions
        if d.kind == "Inject"
        and d.payload.get("pipeline") in ("Backward", "Builder")
        and d.target_id is not None
    }
    overlap_bb = confirm_targets & inject_bb_targets
    if overlap_bb:
        gid = next(iter(overlap_bb))
        return (
            f"batch contains both ConfirmShelve and Inject(Backward/"
            f"Builder) for goal {gid} — the Inject force-reopens the "
            f"target, the ConfirmShelve then shelves it; the queued "
            f"retry would dispatch on a shelved goal. Drop the "
            f"ConfirmShelve (the redispatch already keeps the goal "
            f"alive) or aim the Inject at a different goal."
        )

    # Cross-decision: ConfirmShelve cannot be sent alone (or paired only
    # with other ConfirmShelves / Noops / RequestUserAmend). Forces
    # Strategist to articulate the next step alongside any give-up.
    # Catches three lazy patterns in one rule:
    #   (a) lone first-contact ConfirmShelve — agent gave up without
    #       trying the workflow's natural alternatives.
    #   (b) silent zombie parent strategies — ConfirmShelve(G) where G
    #       is a subgoal of a live parent strategy currently has no
    #       framework-level upward kill (Phase 6 `_propagate_shelve`
    #       is inward-only). Pairing forces the agent to handle the
    #       parent explicitly (Inject(Backward, target=parent) or
    #       Inject(Forward) to build the missing tool).
    #   (c) mass-shelve runs — `[ConfirmShelve, ConfirmShelve, ...]`
    #       with no constructive sibling = bulk give-up.
    # The constructive set deliberately EXCLUDES RequestUserAmend:
    # that's a user-escalation channel reserved for genuinely wrong
    # Defs.lean / Manifest.md, not an escape hatch for "I want to
    # ConfirmShelve without articulating an alternative". If the
    # problem state truly needs both a user amend and a goal shelve,
    # send them in separate Strategist calls (the user-amend pauses
    # dispatch anyway via the awaiting_human gate).
    if any(d.kind == "ConfirmShelve" for d in decisions):
        constructive = sum(
            1 for d in decisions
            if d.kind in ("Inject", "Reopen", "EmitDirective")
        )
        if constructive == 0:
            return (
                "ConfirmShelve cannot be sent alone. Pair it with at "
                "least one constructive decision in the same batch:\n"
                "  - Inject(Forward, brief=...) to build the missing "
                "tool the shelved goal needed.\n"
                "  - Inject(Backward/Builder, target_goal_id=..., "
                "brief=...) to redispatch a different goal (typically "
                "the parent of the shelved subgoal — its strategy will "
                "otherwise stay 'proposed' with an unfeasible subgoal).\n"
                "  - Reopen(target=..., directive=...) to switch focus "
                "to another goal.\n"
                "  - EmitDirective(body=...) to record the learning "
                "(\"X route doesn't work, future strategies avoid\").\n"
                "RequestUserAmend does NOT count as a constructive "
                "pairing — it's reserved for Defs.lean / Manifest.md "
                "errors, not an escape hatch. If both apply, send them "
                "as separate Strategist calls.\n"
                "If you truly mean 'admit defeat on this goal and on "
                "nothing else', pair with EmitDirective explaining "
                "why — silent give-up without articulation is blocked."
            )
    return ""


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
                         trigger_kind: str,
                         forward_batch_id: str | None = None) -> CommitOutcome:
    """Commit one Strategist Inject decision. Dispatches to the
    pipeline-specific helper.

    Batch semantics:
      - `Inject(Forward)` carries a `batch_id` so cascade fires
        `inject_batch_done` once the produced lemma terminates. Multi-
        decision callers pass `forward_batch_id` to share one batch_id
        across N Forward decisions, collapsing N completions into a
        single Strategist wake-up.
      - `Inject(Backward/Builder)` is a redispatch on an existing goal;
        normal cascade handles whatever follows (parent strategy stays
        live, BFS continues). No `batch_id` (no `inject_batch_done`
        fire is needed) but `produced_goal_id=target_id` is kept so
        `propagate_inject_outcome_from_goal` still fills the decision
        row's `outcome` for failure_replay.
    """
    pipeline = decision.payload.get("pipeline")
    if pipeline == "Forward":
        return _commit_inject_forward(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, batch_id_override=forward_batch_id)
    if pipeline in ("Backward", "Builder"):
        return _commit_inject_redispatch(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, pipeline=pipeline)
    raise RuntimeError(
        f"_commit_inject_batch: unhandled pipeline {pipeline!r} "
        f"(verify_decision should have caught this)")


def _commit_inject_forward(decision: Decision, conn: sqlite3.Connection,
                           *, problem: str, tick: int,
                           trigger_kind: str,
                           batch_id_override: str | None = None) -> CommitOutcome:
    """Forward variant — 1 brief → 1 row + 1 Forward enqueue.

    `batch_id_override` lets a multi-decision call share one batch_id
    across all N Inject(Forward) decisions so cascade fires a single
    `inject_batch_done` once every produced lemma terminates. Solo
    (single-decision) calls leave it None and get a fresh batch_id.
    """
    brief = decision.brief.strip()
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()
    row_payload = {
        "pipeline": "Forward",
        "step_index": 0,
        "batch_size": 1,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', NULL, ?, ?, ?, ?, NULL, ?, ?)",
        (problem, tick, trigger_kind, brief,
         decision.reason, json.dumps(row_payload, ensure_ascii=False),
         batch_id, ts, ts),
    )
    row_id = int(cur.lastrowid)
    db.enqueue(
        conn, kind="Forward", target_id=problem,
        target_kind="Problem", priority=10,
        decision_id=row_id,
    )
    db.update_problem_last_strategist_at(conn, problem)
    db.set_problem_bootstrap_done(conn, problem)
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=True,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def _commit_inject_redispatch(decision: Decision, conn: sqlite3.Connection,
                              *, problem: str, tick: int,
                              trigger_kind: str,
                              pipeline: str) -> CommitOutcome:
    """Backward / Builder variant — 1 row + 1 enqueue on target goal.

    `brief` carries the agent's hint for the redispatch. No `batch_id`
    (Strategist does not need to be re-fired when a redispatched goal
    terminates — normal cascade handles propagation upward). The
    `produced_goal_id=target_id` link is kept so
    `propagate_inject_outcome_from_goal` still fills the decision
    row's `outcome` for failure_replay when the target reaches
    proved / shelved / disproved.
    """
    target_id = int(decision.target_id)
    brief = decision.brief.strip()
    ts = db.now()
    row_payload = {
        "pipeline": pipeline,
        "step_index": 0,
        "batch_size": 1,
        "target_goal_id": target_id,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, target_id, brief, reason, payload,"
        " batch_id, produced_goal_id, outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', ?, ?, ?, ?, NULL, ?, NULL, ?, ?)",
        (problem, tick, trigger_kind, target_id,
         brief, decision.reason,
         json.dumps(row_payload, ensure_ascii=False),
         target_id, ts, ts),
    )
    row_id = int(cur.lastrowid)

    # Force-reopen target so BFS / inject dispatch can run on it.
    # Auto-detach if the upward chain has died — same path Strategist
    # Reopen takes. `dead` is a hard terminal already rejected by
    # verify_decision; this list intentionally excludes it.
    g = db.get_goal(conn, target_id)
    if g and str(g["status"]) in ("shelved", "pending_strategist_review",
                                   "frozen"):
        db.update_goal_status(conn, target_id, "open")
        if _dispatcher._has_dead_strategy_in_chain(conn, target_id):
            db.set_goal_detached(conn, target_id, True)

    db.enqueue(
        conn, kind=pipeline, target_id=str(target_id),
        target_kind="Goal", priority=10,
        decision_id=row_id,
    )
    db.update_problem_last_strategist_at(conn, problem)
    db.set_problem_bootstrap_done(conn, problem)
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
        batch_id=None,
        batch_decision_row_ids=[row_id],
    )


def commit_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str, tick: int, trigger_kind: str,
                     workspace: Path) -> list[CommitOutcome]:
    """Execute a multi-decision batch in declared order.

    Caller must have already passed `verify_decisions`. All decisions
    commit; per-kind side effects fire individually. The transaction
    boundary is per-decision (each per-kind helper calls
    `conn.commit()`); a mid-batch raise leaves earlier rows committed,
    which mirrors the existing single-decision contract — verify is
    expected to catch every user-error case, so any raise here
    indicates a framework bug to investigate, not graceful recovery
    territory.

    Multi-decision Inject(Forward) batching: when the list contains
    ≥1 Inject(Forward) decision, all of them share one `batch_id`.
    The `inject_batch_done` Strategist trigger fires once, only after
    every produced lemma terminates. Inject(Backward/Builder) are
    independent — no batch_id, no batch_done fire.

    Returns one CommitOutcome per decision (same order).
    """
    forward_batch_id: str | None = None
    if any(d.kind == "Inject" and d.payload.get("pipeline") == "Forward"
           for d in decisions):
        forward_batch_id = uuid.uuid4().hex
    return [
        _commit_one(d, conn, problem=problem, tick=tick,
                    trigger_kind=trigger_kind, workspace=workspace,
                    forward_batch_id=forward_batch_id)
        for d in decisions
    ]


def commit_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str, tick: int, trigger_kind: str,
                    workspace: Path) -> CommitOutcome:
    """Single-decision wrapper around `commit_decisions`. Preserved
    so existing callers (single-decision tests, anyone hand-driving
    one decision) keep their CommitOutcome-returning contract.
    """
    return commit_decisions(
        [decision], conn, problem=problem, tick=tick,
        trigger_kind=trigger_kind, workspace=workspace,
    )[0]


def _commit_one(decision: Decision, conn: sqlite3.Connection,
                *, problem: str, tick: int, trigger_kind: str,
                workspace: Path,
                forward_batch_id: str | None) -> CommitOutcome:
    """Execute one decision's side effects + INSERT audit row.

    Caller must have already passed `verify_decision`. This is the
    write-path; errors here indicate a bug (or a race with another
    Strategist commit), not user error. `forward_batch_id` is
    threaded through to `_commit_inject_batch` for the multi-decision
    Forward batching case (see `commit_decisions`).
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

    if k == "Inject":
        return _commit_inject_batch(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind,
            forward_batch_id=forward_batch_id,
        )

    if k == "Noop":
        # No side effect beyond the audit row + last_strategist_at.
        pass

    elif k == "EmitDirective":
        db.set_problem_strategist_directive(
            conn, problem, str(decision.payload.get("body", "")).strip()
        )

    elif k == "ConfirmShelve":
        gid = int(decision.target_id)  # type: ignore[arg-type]
        _dispatcher._set_goal_terminal_and_propagate(conn, gid, "shelved")
        _dispatcher._propagate_shelve(conn, gid)
        # Downward cascade removed: shelved is reopenable (split from
        # disproved), descendants of a shelved goal stay invisible to
        # BFS via the alive-set filter in `db.open_goals` regardless
        # of their own status — no behavior gain from flipping them.
        # Strategist's context view filters descendants of dead chains
        # too (see `_section_active_goals`), so the surface area where
        # status drift could mislead Strategist is closed at the view
        # boundary, not the data boundary.

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
      3. self_verify       — parse_decisions + verify_decisions
      4. commit            — commit_decisions side effects
      5. status mapping    — Noop-only batch / schema invalid →
                             infra-reason (no attempts++); commit
                             → success

    Returns `PipelineResult` with one of:
      - outcome='success' on a clean commit (one or more decisions,
        at least one non-Noop)
      - outcome='failed', failure_reason='strategist_noop' when the
        batch contains only Noop decisions (infra so cascade_one
        doesn't burn root.attempts)
      - outcome='failed', failure_reason='strategist_schema_invalid'
        when parse/verify rejects the agent's output (all-or-nothing
        at this stage — no row is committed if any decision fails)
      - outcome='failed', failure_reason='agent_no_output' if no
        decision.json produced
      - provider rc-based reasons (quota / spawn_fast_fail / ...) on
        agent.spawn_llm rc != 0
    """
    from .. import agent
    from ..core import config
    from . import PipelineResult, PROMPT_DIR
    from ..agent.phase2_context import compile_strategist_context

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, problem)
    prompt_path = PROMPT_DIR / "strategist.md"

    # Stage 1 — Context.md
    compile_strategist_context(
        conn, problem=problem, trigger_kind=trigger_kind,
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=pending_review_id,
    )

    # Stage 2 — agent spawn. Mint a session id so a single in-pipeline
    # verify retry can resume the same claude session and see the
    # framework's verify error inline.
    sid = str(uuid.uuid4())
    rc = agent.spawn_llm(
        kind="strategist", prompt_path=prompt_path,
        problem_dir=problem_dir, attempts_dir=attempts_dir,
        session_id=sid,
    )
    if rc != 0:
        return PipelineResult(
            outcome="failed",
            failure_reason=_rc_to_reason(rc),
            failure_detail=f"agent rc={rc}",
        )

    # Stage 3-4 — parse + verify, with one optional retry on verify
    # failure. Parse failures are NOT retried: a malformed decision.json
    # usually means session-level breakage (no clean recovery from
    # re-prompting). Verify failures usually ARE fixable — the rejected
    # reason is informative ("brief missing", "Reopen ancestor is dead",
    # "ConfirmShelve+Inject(B/B) same target", ...). Feeding the error
    # back into the same session and asking for a fresh decision.json
    # converts most of these from "burn a trigger cycle" into "one
    # extra LLM call".
    retry_enabled = config.get(
        "strategist.verify_retry", default=1,
        env_var="ASTERISM_STRATEGIST_VERIFY_RETRY", cast=int,
    ) >= 1
    decision_path = attempts_dir / "decision.json"

    def _read_and_parse() -> tuple[
        list[Decision] | None, str, str
    ]:
        """Returns (decisions, parse_err, missing_reason). When the
        file is missing, missing_reason is non-empty for
        agent_no_output mapping."""
        if not decision_path.exists():
            return None, "", "decision.json not produced"
        try:
            text = decision_path.read_text(encoding="utf-8")
        except OSError as e:
            return None, "", f"decision.json unreadable: {e}"
        ds, perr = parse_decisions(text)
        return ds, perr, ""

    decisions, parse_err, missing = _read_and_parse()
    if missing:
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail=missing,
        )
    if decisions is None:
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"parse: {parse_err}",
        )

    verify_err = verify_decisions(decisions, conn, problem=problem)
    if verify_err and retry_enabled:
        # Single retry on the same session. The provider's `is_retry`
        # path resumes the session and inlines `retry_context` (the
        # verify error) into a Strategist-specific prompt asking for a
        # fresh decision.json.
        rc2 = agent.spawn_llm(
            kind="strategist", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, is_retry=True, retry_context=verify_err,
        )
        if rc2 != 0:
            return PipelineResult(
                outcome="failed",
                failure_reason=_rc_to_reason(rc2),
                failure_detail=(
                    f"verify-retry agent rc={rc2}; "
                    f"first-attempt verify: {verify_err}"
                ),
            )
        decisions, parse_err, missing = _read_and_parse()
        if missing or decisions is None:
            # Treat both as schema_invalid here — the first attempt's
            # decision.json was real but bad, the retry didn't produce
            # a usable replacement.
            detail = missing or f"parse: {parse_err}"
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(
                    f"verify-retry output: {detail}; "
                    f"first-attempt verify: {verify_err}"
                ),
            )
        verify_err2 = verify_decisions(decisions, conn, problem=problem)
        if verify_err2:
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(
                    f"verify-retry: {verify_err2}; "
                    f"first-attempt: {verify_err}"
                ),
            )
        # Retry succeeded — fall through to commit.
    elif verify_err:
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"verify: {verify_err}",
        )

    # Stage 5 — commit + outcome mapping
    if all(d.kind == "Noop" for d in decisions):
        # Pure-Noop batch (one or more Noops): commit audit rows so
        # last_strategist_at + bootstrap_done advance, but map the
        # pipeline outcome to the infra-reason so cascade_one doesn't
        # try to attempts++ on the root. A mixed batch with at least
        # one non-Noop decision falls through to the success path
        # below — there's real work in it.
        try:
            commit_decisions(
                decisions, conn, problem=problem, tick=tick,
                trigger_kind=trigger_kind, workspace=workspace,
            )
        except Exception as e:
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=f"commit raised: {type(e).__name__}: {e}",
            )
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_noop",
            failure_detail=" | ".join(
                str(d.reason or "") for d in decisions
            ),
        )

    try:
        outcomes = commit_decisions(
            decisions, conn, problem=problem, tick=tick,
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

    kinds = ",".join(d.kind for d in decisions)
    row_ids = ",".join(str(o.decision_row_id) for o in outcomes)
    return PipelineResult(
        outcome="success",
        failure_reason="",
        failure_detail=(
            f"committed {len(decisions)} decision(s): [{kinds}] "
            f"(decision_rows=[{row_ids}])"
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
