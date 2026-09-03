"""Strategist decision vocabulary + schema: the `Decision` dataclass,
the frozenset vocabularies (`DECISION_KINDS`, `RETURN_FLAVOURS`,
`TRIGGER_KINDS`, `BATCH_DONE_LIKE`, `_PACKAGE_EXEMPT_KINDS`), `_as_bool`,
and the `decision.json` parser (`parse_decisions` / `parse_decision` /
`_parse_one`).

Split out of `strategist.py` 2026-08-28 (Phase B, B1) unchanged: this is
the pure data-shape layer everything else in the package imports from —
no DB/dispatcher reach-backs, so it has no cross-package imports at all.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# Decision kinds Strategist may emit (subset of the DB CHECK enum —
# the schema still accepts 'Reopen' for legacy rows from before
# 2026-05-28, but the parser/verifier/commit handler no longer
# recognise it; the goal-targeted Inject is the unified reactivation
# mechanism).
DECISION_KINDS: frozenset[str] = frozenset({
    "Inject", "ConfirmShelve", "EmitDirective",
    "RequestUserAmend", "Noop", "MarkDeliverable", "Ingest",
    # "AttemptDisproof" retired 2026-08-04 (kept parseable, like
    # EmitDirective, so the verifier can teach the way out): one use
    # all-time — its own acceptance test. The bet-against-a-claim move
    # is expressed with the general machinery instead: Inject a Forward
    # mint of the precise negation / counterexample; a sub-group hands
    # a refuted charter back via ReturnToParent(refuted); a false USER
    # claim goes to RequestUserAmend with the disproof attached.
    "FetchPaper", "AttemptDisproof",
    # v35 (discussion_group_design.md) — hand a claim DOWN to a new
    # sub-group, and hand a charter back UP to the parent group.
    "Delegate", "ReturnToParent",
    # The reverse of Delegate: a parent retires a child whose line its
    # own route no longer needs.
    "CloseGroup",
})

#: The three shapes a `ReturnToParent` can take. They differ in what the
#: parent gets back, and each carries its own mechanical requirement —
#: 'refuted' most of all: claiming a refutation without a kernel-checked
#: negation is exactly the shape the framework never accepts on trust.
RETURN_FLAVOURS: frozenset[str] = frozenset(
    {"refuted", "amend", "exhausted"})


#: One column, three contracts: the `brief` column's CONTRACT NAME per
#: kind (`_parse_one` reads the decision.json key of that name into it).
#: Both the parser and the renderer that shows a decision to the judge
#: need this mapping, and a second copy is how a rendered label drifts
#: from the field the contract actually names.
BRIEF_FIELD_DEFAULT = "brief"
BRIEF_FIELD_BY_KIND: dict[str, str] = {"Inject": "proof",
                                       "Delegate": "charter"}


def brief_field(kind: str) -> str:
    """The decision.json key whose value lands in `Decision.brief`."""
    return BRIEF_FIELD_BY_KIND.get(kind, BRIEF_FIELD_DEFAULT)


def _as_bool(v: Any) -> bool:
    """Coerce a config value (yaml bool or string) to bool."""
    return v if isinstance(v, bool) else \
        str(v).strip().lower() in ("1", "true", "yes", "on")

# Trigger kinds (mirrors strategist_decisions.trigger_kind CHECK enum).
TRIGGER_KINDS: frozenset[str] = frozenset({
    # Retired at runtime — the DB CHECK keeps the values for old rows:
    # "first_launch" (Phase 6: fresh problem = initial stall →
    # inject_batch_done wake); "audit" (2026-07-25: the v26 epistemic
    # auditor's belief sweep is now phase 1 of the routine wake).
    "pending_review", "routine",
    "inject_batch_done",
    # T4 structural-stall rescue (first-class since 2026-08-24, v43 —
    # was conflated with inject_batch_done, leaving the rescue rate
    # grep-only). Behaves as inject_batch_done everywhere; only the
    # recorded identity differs.
    "stall",
    # The action wake a FIRED routine audit seats (2026-08-30): the
    # batch-done conversation with the audit's findings on top of its
    # Context, and a verify rule that every fired root is acted on.
    "routine_fired",
})

#: A stall wake IS a batch-done wake behaviorally — same prompt, same
#: mandatory-advance rule, same reopen-promise section. Branch points
#: test membership here, never `== "inject_batch_done"`, so the split
#: identity cannot silently drop one of the two.
BATCH_DONE_LIKE: frozenset[str] = frozenset({"inject_batch_done", "stall",
                                              "routine_fired"})

# Research mode (research_mode_design.md §1) — the proposal-package
# gate keys on decision SHAPE: a batch wholly within the exempt kinds
# moves no route (literature intake / hand-back / no-op). Any other
# batch must carry a Programme proposal (four sections in
# `proposal.md`) and pass the Adversary.
_PACKAGE_EXEMPT_KINDS: frozenset[str] = frozenset(
    # `ReturnToParent` joins the hand-back family: the group is ending,
    # so there is no next batch for a Programme revision to argue for.
    # `MarkDeliverable` joined when the wake split retired (2026-08-11):
    # it records that work already dispatched, already argued and already
    # kernel-checked is the deliverable. Demanding a fresh Programme
    # revision to say so would be friction the un-judged admin turn never
    # charged. A mark riding a batch that DOES move the route is gated
    # with it — `package_gate_applies` asks whether ANY kind is
    # non-exempt.
    {"FetchPaper", "RequestUserAmend", "Noop", "ReturnToParent",
     "MarkDeliverable"})


# ---------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------

@dataclass
class Decision:
    """Parsed Strategist decision. Mirrors `docs/archive/design/phase2/pipelines.md`
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

# (resolve_directive_body_files retired 2026-08-19: the `*_file`
# hand-off shipped 07-19 against JSON-escaping corruption and was
# measured at ZERO uses across 1,174 Injects / 103 Delegates / every
# EmitDirective — its only living consumer was the retired kind. If
# escaping corruption ever returns, design against the observed shape
# rather than reviving an affordance nobody reached for.)


def parse_decisions(json_text: str) -> tuple[list[Decision] | None, str]:
    """Parse the agent's `decision.json` content into a list of decisions.

    Multi-decision schema: top-level is a JSON array of one or more
    decision objects. Single-decision back-compat: a top-level dict is
    accepted and wrapped as `[dict]` so agents that still emit one
    object work unchanged. Returns (decisions, '') on success or
    (None, error_message) on any malformed item.
    """
    try:
        # strict=False admits raw control characters INSIDE string
        # values (a literal newline in a reason field) — and nothing
        # else. Models emit these routinely; the meaning is exactly the
        # escaped form, and dying for one cost a 10-minute research
        # wake (p324, 2026-08-25). Structural damage (truncation,
        # trailing garbage) still fails below.
        obj = json.loads(json_text, strict=False)
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
    # One column, three contracts (2026-08-11; Delegate reshaped
    # 2026-08-19). An Inject's prose is the argument that settles its
    # brick — the part of the batch's `## Proof` the author copied
    # across — so the key it is written under is `proof`. A Delegate's
    # is the CHARTER: the claim a new group must settle, written under
    # `charter` (its old key `brief` now names the optional guidance
    # hand-off instead — see below). Naming them apart is what stops
    # each contract teaching the other's meaning; they share a row
    # because a decision carries one piece of prose, not because the
    # prose means one thing.
    brief = obj.get(brief_field(kind))
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
                 "brief", "proof", "reason", "payload", "charter"):
            continue
        payload[k] = v
    # Delegate's `brief` (2026-08-19 contract): guidance and lessons
    # handed to the group — payload data the child's context renders,
    # never part of the judged charter. (Historical rows: a Delegate
    # `brief` column value from before this reshape IS the charter.)
    if kind == "Delegate" and obj.get("brief"):
        payload["brief"] = obj["brief"]
    return Decision(kind=kind, target_id=target_id, brief=brief,
                    reason=reason, payload=payload), ""


