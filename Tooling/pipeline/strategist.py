"""Phase 2 — Strategist pipeline (Step 6 scaffolding).

Strategist emits a single meta-level decision per invocation:
  Inject / ConfirmShelve / Reopen / EmitDirective
  / RequestUserAmend / Noop

This module covers decision validation + commit; the agent stage
(actually spawning the LLM, writing `decision.json` to attempts_dir)
is the next-session piece. The framework-side logic — schema check,
Reopen ancestor safety walk, atomic side effects, strategist_decisions
audit row, last_strategist_at touch — is implemented in full.

Stage order (docs/archive/design/phase2/pipelines.md §2.4):
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
import re as _re
import sqlite3
import tempfile
import time as _time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..state import db, failures as _failures, transitions
from ..state import groups as _groups
from ..core import dispatcher as _dispatcher


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
})

#: A stall wake IS a batch-done wake behaviorally — same prompt, same
#: mandatory-advance rule, same reopen-promise section. Branch points
#: test membership here, never `== "inject_batch_done"`, so the split
#: identity cannot silently drop one of the two.
BATCH_DONE_LIKE: frozenset[str] = frozenset({"inject_batch_done", "stall"})

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
PROPOSAL_BASENAME = "proposal.md"


def package_gate_applies(decisions, trigger_kind: str | None) -> bool:
    return any(d.kind not in _PACKAGE_EXEMPT_KINDS for d in decisions)


def verify_proposal_package(decisions, attempts_dir) -> tuple[
        "str | None", "dict[str, str] | None", "str | None"]:
    """Package-side checks for a gated batch: proposal file present,
    four-section contract, and the ≥1-experiment rule (endgame batches
    exempt). Returns (body, sections, err)."""
    from ..state import programme
    path = attempts_dir / PROPOSAL_BASENAME
    if not path.exists():
        return None, None, (
            "this batch moves the route, so it must carry a Programme "
            f"proposal: Write `{PROPOSAL_BASENAME}` (bare filename, in "
            "your attempts dir) with the four sections `# <Title>`, "
            "`## Argument`, `## Proof`, `## Roadmap`. Then re-emit "
            "decision.json (unchanged if it was already right).")
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as e:
        return None, None, f"{PROPOSAL_BASENAME} unreadable: {e}"
    sections, err = programme.parse_proposal(body)
    if err:
        return None, None, err
    # The ≥1-experiment quota lived here until 2026-08-16 (owner
    # ruling). A per-batch quota gets satisfied with manufactured
    # experiments — the same pathology as the stalled-root Inject tax —
    # while the actual invariant ("a batch must not leave the group in
    # dead air") is already enforced mechanically by the stalled-delta
    # gate and the parked-root gate in `verify_decisions`, both of which
    # fire on STATE, not on decision-kind counts.
    # The `Roadmap:` presence check is GONE (2026-08-11). Its history is
    # the argument: it began as a substring match of the cited phrase
    # against the free-prose Roadmap — a gate detecting free text, which
    # the design rules forbid — and it bounced whole batches five times
    # over phrasing (2026-08-03 feedback #4, operator ruling: the Roadmap
    # stays pure NL). What survived that narrowing checked only that SOME
    # line began `Roadmap:`, which `Roadmap: x` satisfies. It could not
    # fail a batch that was actually wrong and it could fail one that was
    # right, while remaining the last mechanical reader of a field the
    # Strategist writes as prose. Whether an experiment tests the entry
    # it claims is the Adversary's, under criteria 1/4, and always was.
    return body, sections, None


def _format_rebuttal(verdict: dict, round_no: int,
                     rounds_left: int,
                     length_warn: "str | None" = None) -> str:
    crits = "\n".join(f"- {c}" for c in verdict.get("criticisms", []))
    # 07-29 bloat ruling: revisions must not answer objections by
    # accretion (observed: each rebut round ADDED argumentation;
    # proposal 31.6k on a toy batch). The base sentence rides every
    # rebuttal; the over-budget escalation appears only when a length
    # warning actually tripped — a rare line keeps its force.
    over = (f"\n{length_warn}\nThe revision must come back smaller.\n"
            if length_warn else "")
    return (
        f"ADVERSARY REBUTTAL (round {round_no}; {rounds_left} revision "
        "round(s) left before this proposal is discarded and the next "
        "wake restarts fresh):\n" + crits + "\n" + over +
        "For EACH point: either revise (rewrite proposal.md — and "
        "decision.json if the experiments change) or defend (keep your "
        "position and answer the point inside `## Argument`). Revise by "
        "cutting and correcting in place, not by appending defenses. "
        "Do not concede points you believe are misreadings. Re-emit "
        "decision.json in every case.")


# Files allowed in RequestUserAmend(file=...).
# Root.lean joined 2026-07-08 (feature D live livelock): a FALSE root
# claim is amendable — before this, the hand-back verb could not
# point at the file that was wrong and the Strategist looped on
# schema_invalid forever.
# v40 (Manifest retirement): 'charter' is the DB-resident goal (the
# top group's charter) — an accepted amend on it writes through
# state/intent.set_charter, not a file. The user's WORD is deliberately
# absent: standing directives are never machine-amendable.
USER_AMEND_FILES: frozenset[str] = frozenset(
    {"Defs.lean", "Root.lean", "charter"})

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
    if kind == "Inject":
        brief = obj.get("proof")
    elif kind == "Delegate":
        brief = obj.get("charter")
    else:
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


# ---------------------------------------------------------------------
# Schema validation (self_verify stage)
# ---------------------------------------------------------------------

def _authoring_group(conn: sqlite3.Connection, problem: str,
                     group_id: "int | None"):
    """The group whose Strategist is emitting this batch.

    `group_id` comes from the queue row that seated this wake. It is
    optional only so hand-driven callers (tests, one-off scripts) keep
    working: they mean the top group, which is what a problem's single
    Strategist always was."""
    if group_id is not None:
        row = _groups.get(conn, int(group_id))
        if row is not None:
            return row
    return _groups.top_group(conn, problem)


def _group_retired_status(conn: sqlite3.Connection, problem: str,
                          group_id: "int | None") -> "str | None":
    """The authoring group's terminal status, or None while it is live.

    The group-side mirror of Backward's goal race-guard: a group can be
    retired mid-wake (an ancestor's ReturnToParent cascades `closed`
    under it) and the wake finds out only by asking. Measured 2026-08-19
    (fold day): g464/g485 were closed at 11:02Z and their in-flight
    wakes debated on to adversary round 11 — every round after the flip
    was spent on a batch that had nowhere legal to land.

    Resolves through `_authoring_group`, so `group_id=None` means the
    top group — a post-Ingest ghost wake on a delivered top group is the
    same disease (2026-08-13/14: groups 383/381, four batches on
    delivered charters)."""
    row = _authoring_group(conn, problem, group_id)
    if row is None:
        return None
    status = str(row["status"])
    return status if status in _groups.TERMINAL_STATUSES else None


def verify_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str,
                    workspace: "Path | None" = None,
                    group_id: "int | None" = None,
                    prior_decisions: "list[Decision] | None" = None) -> str:
    """Validate decision shape + cross-row constraints. Returns '' if
    OK, an error message string otherwise.

    Checks:
      - Required fields per decision kind
      - target_id exists in goals (when set)
      - Inject mode is shape-derived (target present = goal job,
        absent = mint); legacy `pipeline` payload is ignored
      - Reopen ancestor safety walk (no `disproved` ancestor)
      - RequestUserAmend file ∈ USER_AMEND_FILES
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
            # Two wakes were bounced back-to-back on this exact shape
            # (2026-08-22): the slug named a brick ANOTHER Inject in the
            # same batch was about to mint. A batch's decisions run in
            # parallel — a mint has no goal id until it lands, so
            # targeting it is structurally impossible, and the old
            # message ("use the integer id") named an id that cannot
            # exist yet.
            return (f"target_id={decision.target_id!r} (slug) not found "
                    f"in problem {problem!r}. If this slug is minted by "
                    f"another Inject in THIS batch: a batch's decisions "
                    f"run in parallel and cannot target each other — "
                    f"fold the dependent step into that mint's own "
                    f"proof, or dispatch it next wake once the brick "
                    f"lands. If a PRIOR batch was to mint it: that mint "
                    f"died before creating the goal (check its outcome "
                    f"in `## Completed Inject batches`) — re-mint it "
                    f"rather than target it. Otherwise use the integer "
                    f"goal id shown in Context.md's active goal list")
        decision.target_id = int(row["id"])

    if k == "Inject":
        # Shape-derived mode (update_plan_2026_07 #1): `target_goal_id`
        # present → work that goal (the Formalizer decides prove-vs-
        # split itself — steer with the brief's mathematics, not a
        # mode); absent → mint ONE new brick from the brief. The legacy
        # `pipeline` payload field is ignored when present.
        if not isinstance(decision.brief, str) or not decision.brief.strip():
            # Emptiness is the only mechanical check here, and it stays
            # that way. A length floor cannot tell a genuinely short
            # argument from padding — it fails the right batch and
            # passes the wrong one, which is what retired the `Roadmap:`
            # check on this same field. The reader who CAN tell is the
            # worker, and `return_to_nl` is how it says so.
            return ("Inject requires non-empty `proof` (string): the part "
                    "of this batch's `## Proof` that settles this brick, "
                    "copied across with the vocabulary it uses")
        if (decision.payload.get("briefs") or decision.payload.get("directive")
                or decision.payload.get("brief")):
            return (f"Inject schema uses top-level `proof: str`; "
                    f"`brief` / `briefs` / `directive` fields are legacy "
                    f"— remove them and put the argument in `proof`")
        target = decision.target_id
        if target is None:
            return ""          # mint shape — brief is the whole payload
        g = db.get_goal(conn, int(target))
        if g is None:
            return f"target_goal_id={target} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem "
                    f"{g['problem']!r}, not {problem!r}")
        if str(g["status"]) in ("proved", "dead"):
            return (f"target_goal_id={target} is {g['status']!r}; "
                    f"Inject cannot redispatch a terminal goal. "
                    f"proved/dead are hard terminals; "
                    f"open a different angle on a different goal instead.")
        # `disproved` passes on purpose (2026-08-18): it is parked on a
        # CLAIMED counterexample, not a kernel verdict, and an Inject on
        # it IS the revival route — argue in the proof why the claimed
        # counterexample fails. The ancestor walk below still blocks
        # descendants of one (revive the ancestor itself first).
        # Ancestor safety walk (was Reopen's responsibility pre-2026-05-28;
        # now the goal-targeted Inject takes over as the unified
        # reactivation mechanism). disproved ancestor = counterexample
        # already shown for a parent statement; descendant is moot. dead
        # ancestor is also a hard terminal (parent strategy was wrong);
        # commit's auto-detach handles `shelved` chains but not these.
        bad, anc_kind = _dispatcher._has_hard_terminal_ancestor(
            conn, int(target))
        if bad:
            if anc_kind == "disproved":
                return (
                    f"Inject rejected: goal {target} has a "
                    f"'disproved' ancestor (a counterexample was "
                    f"claimed for a parent statement, so this "
                    f"descendant is moot as long as that stands). "
                    f"If you believe the parent claim after all, "
                    f"Inject the disproved ancestor itself — that "
                    f"revives it. Otherwise ConfirmShelve."
                )
            return (
                f"Inject rejected: goal {target} has a "
                f"'dead' ancestor (parent strategy was wrong; this "
                f"descendant exists only in that abandoned context). "
                f"Inject(target=<parent-goal>) to try a "
                f"different decomposition instead."
            )
        return ""

    if k == "Noop":
        if not decision.reason or not str(decision.reason).strip():
            return "Noop requires non-empty reason"
        return ""

    if k == "Delegate":
        # Reshaped 2026-08-19 (owner wording): `charter` is the claim
        # the group is judged against, `reason` is the parent-side
        # justification the judge rules on, `brief` (optional payload)
        # is guidance handed to the child. The old three-heading
        # research-proposal check retired with the split — the fan rule
        # and the depth cap carry the structural burden now, and the
        # judge rules on substance.
        if not decision.brief or not str(decision.brief).strip():
            return ("Delegate requires a `charter`: the kernel-checkable "
                    "research item this group exists to settle, stated "
                    "precisely enough that 'is it settled?' has an "
                    "answer")
        if not decision.reason or not str(decision.reason).strip():
            return ("Delegate requires a `reason`: why you cannot prove "
                    "this yourself and `Inject` it, nor pace it through "
                    "AHEAD batch by batch — why it must be a group's "
                    "burden")
        charter = str(decision.brief).strip()
        parent = _authoring_group(conn, problem, group_id)
        if parent is None:
            return ("Delegate has no authoring group; the problem's top "
                    "group is missing (framework bug — a problem without "
                    "one has no Strategist seat at all)")
        # Hard depth cap (owner ruling 2026-08-19): ancestry count is
        # the whole check — structured signal, never charter prose.
        if _groups.depth(conn, int(parent["id"])) >= _groups.GROUP_DEPTH_CAP:
            return ("Delegate is unavailable at your depth — the group "
                    "tree caps two levels below the top. Plan the work "
                    "as follow-up batches in your Roadmap's AHEAD (the "
                    "next wake fires when this batch completes), or, if "
                    "your charter itself needs recutting, hand it back "
                    "with `ReturnToParent(amend)`.")
        # Byte-identical duplicate of a LIVE sibling: two groups working
        # the same charter is double-dispatch, not parallelism. A charter
        # a sibling RETURNED is deliberately allowed through — retrying a
        # failed line is legitimate, and judging whether this attempt
        # differs is the Adversary's call, not a string comparison's
        # (the same reason task #112's dead-twin gate misfires).
        dup = conn.execute(
            "SELECT id FROM groups WHERE parent_group_id = ?"
            "   AND status = 'active' AND charter = ?",
            (int(parent["id"]), charter)).fetchone()
        if dup is not None:
            return (f"Delegate duplicates live group {dup['id']}: its "
                    f"charter is byte-identical to this one. Wait for it, "
                    f"or delegate the part it is NOT covering")
        if decision.target_id is not None:
            g = db.get_goal(conn, decision.target_id)
            if g is None:
                return f"target_goal_id={decision.target_id} not found"
            if str(g["problem"]) != problem:
                return (f"target goal belongs to problem {g['problem']!r}, "
                        f"not this Strategist's {problem!r}")
            if str(g["status"]) in transitions.GOAL_HARD_TERMINALS:
                return (f"target g{decision.target_id} is "
                        f"{g['status']!r} — a settled goal has nothing "
                        f"for a group to work")
            anchored = conn.execute(
                "SELECT id FROM groups WHERE anchor_goal_id = ?",
                (int(g["id"]),)).fetchone()
            if anchored is not None:
                return (f"g{decision.target_id} already anchors group "
                        f"{anchored['id']}; promote a different goal or "
                        f"work through that group")
        return ""

    if k == "CloseGroup":
        me = _authoring_group(conn, problem, group_id)
        if me is None:
            return "CloseGroup has no authoring group (framework bug)"
        target = decision.payload.get("target_group_id")
        try:
            target = int(target)
        except (TypeError, ValueError):
            return ("CloseGroup requires `target_group_id` — the child "
                    "group you are retiring")
        kid = _groups.get(conn, target)
        if kid is None or str(kid["problem"]) != problem:
            return f"group {target} not found in this problem"
        # Own children only. A grandchild belongs to ITS parent, and a
        # cousin to nobody here — reaching past one level would let a
        # group cancel work it never commissioned and cannot judge.
        if kid["parent_group_id"] is None or                 int(kid["parent_group_id"]) != int(me["id"]):
            return (f"group {target} is not yours to close — you may "
                    f"retire only the groups you opened")
        if str(kid["status"]) != _groups.ACTIVE:
            return (f"group {target} already reached "
                    f"{kid['status']!r}; nothing to close")
        if not decision.reason or not str(decision.reason).strip():
            return ("CloseGroup requires a non-empty reason: what "
                    "changed in YOUR route that makes this line "
                    "unnecessary. Difficulty is not a reason — whether "
                    "to give up is the group's own call")
        return ""

    if k == "ReturnToParent":
        me = _authoring_group(conn, problem, group_id)
        if me is None:
            return ("ReturnToParent has no authoring group (framework "
                    "bug)")
        # The structural wall: the top group has no parent to return to,
        # so the difficulty escape hatch cannot reach the human channel.
        # `RequestUserAmend` stays what it is — for a WRONG user file.
        if _groups.is_top(me):
            return ("ReturnToParent is not available to the top group: "
                    "there is no parent to hand the charter back to. "
                    "Difficulty is work, not a wrong user file — keep "
                    "going, or delegate the part that is blocking you")
        if str(me["status"]) != _groups.ACTIVE:
            return (f"this group already reached {me['status']!r}; a "
                    f"charter can only be handed back once")
        flavour = decision.payload.get("flavour")
        if flavour not in RETURN_FLAVOURS:
            return (f"ReturnToParent.flavour must be one of "
                    f"{sorted(RETURN_FLAVOURS)} (got {flavour!r})")
        if not decision.reason or not str(decision.reason).strip():
            return ("ReturnToParent requires a non-empty reason — the "
                    "post-mortem the parent decides on: what was tried, "
                    "where it died, what was learned")
        if flavour == "refuted":
            # A refutation is a mathematical claim like any other, and
            # the framework never takes one on trust: name the proved
            # brick that carries the negation.
            if decision.target_id is None:
                return ("ReturnToParent(refuted) requires "
                        "`target_goal_id` — the PROVED node carrying the "
                        "negation. A refutation asserted without one is "
                        "an opinion")
            g = db.get_goal(conn, decision.target_id)
            if g is None:
                return f"target_goal_id={decision.target_id} not found"
            if str(g["problem"]) != problem:
                return (f"target goal belongs to problem {g['problem']!r}, "
                        f"not this Strategist's {problem!r}")
            if str(g["status"]) != "proved":
                return (f"ReturnToParent(refuted) target g{g['id']} is "
                        f"{g['status']!r}, not 'proved' — settle it "
                        f"first, or return `exhausted` instead")
        if flavour == "amend":
            proposed = decision.payload.get("proposed_charter")
            if not isinstance(proposed, str) or not proposed.strip():
                return ("ReturnToParent(amend) requires "
                        "`proposed_charter`: the corrected claim you "
                        "believe IS provable. Without one this is "
                        "`exhausted`")
            if proposed.strip() == str(me["charter"]).strip():
                return ("ReturnToParent(amend).proposed_charter is "
                        "identical to the charter you were given — say "
                        "what should change, or return `exhausted`")
        return ""

    if k == "EmitDirective":
        # Retired 2026-08-03 (research_mission_design.md §3.1): every
        # directive on record carried conventions or process lessons,
        # and keeping them in a second document let a directive
        # contradict the brief it governed. One source now.
        return ("EmitDirective is retired — standing worker guidance "
                "lives in the Programme: add or revise a "
                "`## Conventions` section in this revision's "
                "proposal.md instead (it is optional, comes after "
                "`## Roadmap`, and workers receive it verbatim)")

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

    if k == "MarkDeliverable":
        if decision.target_id is None:
            return "MarkDeliverable requires target_goal_id"
        g = db.get_goal(conn, decision.target_id)
        if g is None:
            return f"target_goal_id={decision.target_id} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem {g['problem']!r}, "
                    f"not this Strategist's {problem!r}")
        # Only framework-GENERATED nodes are deliverables the human must
        # vouch for; a hand-written root/Defs is already author-vouched.
        if str(g["origin"]) != "forward":
            return (f"MarkDeliverable target must be a Forward-produced node "
                    f"(origin='forward'); goal {decision.target_id} is "
                    f"origin={g['origin']!r}")
        # FSM §3.2 (2026-07-12): marking is a real edge only for a PROVED,
        # not-yet-marked node — an unproved mark is a promise the review
        # cannot vouch, and a re-mark is a no-op that must not read as
        # progress.
        if str(g["status"]) != "proved":
            return (f"MarkDeliverable target g{decision.target_id} is "
                    f"{g['status']!r} — only a PROVED node can be marked")
        if int(g["is_deliverable"] or 0):
            # SHAREABLE, not first-come-first-served (owner ruling
            # 2026-08-17). `is_deliverable` is problem-global, but the
            # Ingest gate counts a GROUP's marks from its own
            # `MarkDeliverable` rows — so a blanket rejection here let
            # group A mark a brick and strand group B behind "already
            # marked" with no way to record that the same proved result
            # settles ITS charter too. Cross-crediting is the AND/OR
            # design working (420 closed 425 precisely because an
            # independent route proved its certificate); only a re-mark
            # by the SAME group is the no-op FSM §3.2 forbids reading
            # as progress.
            me = _authoring_group(conn, problem, group_id)
            mine = me is not None and conn.execute(
                "SELECT 1 FROM strategist_decisions"
                " WHERE decision_kind = 'MarkDeliverable'"
                "   AND target_id = ? AND group_id = ? LIMIT 1",
                (int(decision.target_id), int(me["id"]))).fetchone()
            if mine:
                return (f"goal g{decision.target_id} is already marked "
                        f"by YOUR group — re-marking changes nothing (a "
                        f"rollback clears the mark; re-marking after "
                        f"that is legal)")
        return ""

    if k == "FetchPaper":
        # Retired 2026-08-22 (owner ruling): paper fetching is now the
        # Strategist's OWN tool surface, not a delegated spawn — the
        # decision round-trip and the Scholar pipeline it fed are gone.
        return ("FetchPaper is retired — fetch papers yourself, during "
                "this wake: `paper_search(query=...)` (or `doi=...`) "
                "resolves open copies with direct pdf_url locations, "
                "then `paper_fetch(target=<url|arxiv id>, "
                "problem=<this problem>, reason=...)` downloads, "
                "shelves and binds in one call.")

    if k == "AttemptDisproof":
        # Retired 2026-08-04 (one use all-time — its own acceptance
        # test; the real counterexample work always went through mints).
        # The general machinery expresses the same bet.
        return ("AttemptDisproof is retired — bet against a claim with "
                "the general machinery: `Inject` a Forward mint stating "
                "the precise negation (or a counterexample construction) "
                "and let the kernel settle it. A sub-group hands a "
                "refuted charter back via `ReturnToParent(refuted)` "
                "naming that proved node; a false USER claim goes to "
                "`RequestUserAmend` with the disproof attached")

    if k == "Ingest":
        # Phase 6 — Ingest is the ONLY terminal (Done fused into it).
        # HARD gate: a present root is a user-pinned must-prove-exactly-
        # this requirement, machine-checkable; the framework rejects the
        # terminal judgment outright while it is unproved. (The charter's
        # other requirements are SOFT — NL, only the Strategist can judge
        # them — so they are prompt-governed, not gated here.)
        #
        # v35 — a SUB-group's Ingest is a delivery upward, and the same
        # gate applies one level down, because the same equation holds:
        # charter is its judgment subject and its ANCHOR is its root goal. So a
        # rescue-shape group must prove its anchor; an anchorless one
        # must have marked at least one deliverable of its own.
        me = _authoring_group(conn, problem, group_id)
        if me is not None and not _groups.is_top(me):
            anchor = me["anchor_goal_id"]
            if anchor is not None:
                g = db.get_goal(conn, int(anchor))
                if g is None or str(g["status"]) != "proved":
                    return (f"Ingest is blocked: this group's anchor "
                            f"g{anchor} is "
                            f"{(g['status'] if g else 'missing')!r}, not "
                            f"'proved'. Delivering a charter you have not "
                            f"settled is what `ReturnToParent` is for")
            elif not db.deliverables(conn, problem=problem,
                                     group_id=int(me["id"])):
                # Same-batch marks count — but only those LISTED BEFORE
                # this Ingest (commit processes in declared order, so
                # earlier marks are persisted by the time the Ingest
                # commits). Without this, an anchorless group whose
                # charter is already settled was in a catch-22 measured
                # 2026-08-16 (grp 422 rev 438, ten rounds): mark-only
                # bounced off the parked-root gate, mark+Ingest bounced
                # here because the mark was not yet a row. A claude-era
                # strategist stated this exact mechanism and its judge
                # prosecuted the claim as an unsourced guess — it was
                # true (rev 346).
                if not any(d.kind == "MarkDeliverable"
                           for d in (prior_decisions or [])):
                    return ("Ingest requires at least one deliverable "
                            "THIS group marked (`MarkDeliverable`) — the "
                            "bricks the group above you will cite. A "
                            "same-batch mark counts when it is listed "
                            "BEFORE the Ingest in decision.json")
            return ""
        root = conn.execute(
            "SELECT status FROM goals WHERE problem = ? AND"
            " origin = 'root' LIMIT 1", (problem,)).fetchone()
        root_proved = root is not None and str(root["status"]) == "proved"
        if root is not None and not root_proved:
            return ("Ingest is blocked: this problem has a root goal "
                    f"(status={root['status']!r}) that must be proved "
                    "before the terminal judgment is valid")
        # A proved root counts toward the >=1-deliverable requirement:
        # a pure-root problem (no Forward deliverables, e.g. a classic
        # single-theorem charter) must still be able to exit. Same-batch
        # marks listed before the Ingest count too — the same catch-22
        # fixed for anchorless sub-groups above applies to a pure-NL
        # problem's top group.
        if not db.deliverables(conn, problem=problem) and not root_proved \
                and not any(d.kind == "MarkDeliverable"
                            for d in (prior_decisions or [])):
            return ("Ingest requires at least one marked deliverable "
                    "(MarkDeliverable) or a proved root goal; a same-batch "
                    "mark counts when listed BEFORE the Ingest")
        # The tree must be ACCOUNTABLE before it becomes terminal.
        # `proof_store.inventory` is the framework's DB↔file oracle and
        # it had exactly one caller — the operator typing `asterism
        # drift-check` — so across a 13-hour unattended run nothing ever
        # asked it (2026-07-30). Ingest is both the moment it matters
        # (this publishes the snapshot) and a place where the question is
        # answerable: unlike the per-spawn audit, which cannot tell a
        # concurrent legal commit from tampering, the oracle only needs
        # the tree to agree with the DB.
        from ..state import proof_store as _proof_store
        drift = (_proof_store.inventory(conn, workspace, scope=problem)
                 if workspace is not None else None)
        if drift is not None and not drift.ok():
            print(f"[strategist] Ingest({problem}) blocked by DB↔file "
                  f"drift: {drift.summary()}; run `asterism drift-check` "
                  f"— operator must resolve", flush=True)
            return (f"Ingest blocked: {drift.summary()} — the proofs tree "
                    f"does not agree with the DB, so the snapshot would "
                    f"describe something that is not there. A human must "
                    f"resolve it (`asterism drift-check`)")
        # (The AttemptDisproof-linked disproof gate retired with the
        # kind, 2026-08-04 — no mechanically-linked negation pairs can
        # be minted anymore. The invariant "a disproved requested claim
        # never satisfies the charter" survives in the contract line
        # plus the judge's reachability criterion: a refuted main claim
        # leaves no Roadmap entry that could close it.)
        return ""

    if k == "RequestUserAmend":
        # v35 — the mirror of the `ReturnToParent` wall. Only the group
        # that FACES the human may speak to them, for two reasons: the
        # side effect (`awaiting_human`) freezes the whole problem
        # including every sibling group, and a sub-group cannot see the
        # tree-wide context the human needs to judge the request. A
        # sub-group that finds a user file genuinely wrong returns the
        # charter with that finding; the parent carries it up, and the
        # top group asks. Without this the difficulty escape hatch just
        # walks in the side door — the one with the larger blast radius.
        me = _authoring_group(conn, problem, group_id)
        if me is not None and not _groups.is_top(me):
            return ("RequestUserAmend is the TOP group's channel — it "
                    "pauses the whole problem, siblings included, and "
                    "the human needs context you cannot see from here. "
                    "Return the charter instead (`ReturnToParent`), "
                    "naming the file and what is wrong with it; the "
                    "group above you carries it up.")
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
        # FSM §3.3 (2026-07-12, human-attention guard): a request byte-
        # identical to one the user already adjudicated re-asks the same
        # question — mechanical reject; a changed proposal is a new ask.
        prior = conn.execute(
            "SELECT payload FROM strategist_decisions"
            " WHERE problem = ? AND decision_kind = 'RequestUserAmend'"
            "   AND outcome IS NOT NULL AND outcome != 'awaiting_human'",
            (problem,)).fetchall()
        for r in prior:
            try:
                prev_body = json.loads(r["payload"] or "{}").get(
                    "proposed_body")
            except ValueError:
                continue
            if prev_body == proposed_body:
                return (
                    "RequestUserAmend rejected: this proposed_body is "
                    "byte-identical to a request the user already "
                    "adjudicated — re-asking the same question costs "
                    "human attention and changes nothing. Amend the "
                    "proposal or keep working the problem."
                )
        return ""

    return f"verify_decision: unhandled kind {k!r}"


#: The wake split is RETIRED (2026-08-11; it ran from 2026-08-03).
#:
#: Turn A existed to keep registry chores off the math turn's attention.
#: Measured over the union_closed run: 43 batches, and Turn A produced
#: 18 MarkDeliverable + 4 Noop + 0 RequestUserAmend — it was offloading
#: less than it cost, at one spawn and one Context per wake.
#:
#: What decided it was the exit condition. `Ingest` was a math kind and
#: `MarkDeliverable` — its precondition — was an admin kind, so the
#: terminal judgement was split across two turns and "mark, then Ingest"
#: could not happen in one wake. Turn A running FIRST hid that: the
#: marks a wake saw were the previous wake's. The ordering was load
#: -bearing for a defect the split introduced.
#:
#: The isolation argument did not survive reading its own prompt either:
#: admin.md said "Mark only top-level claims the charter asks for" and
#: "Do not reason about the mathematics" — which claims are the
#: deliverable IS a mathematical judgement.
#:
#: Both kinds now live in the one turn, and a mark that rides a batch
#: carrying an argument is judged with it (a mark-only batch has no
#: argument to judge, and stays exempt — see `_PACKAGE_EXEMPT_KINDS`).


def verify_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str,
                     workspace: "Path | None" = None,
                     trigger_kind: str = "",
                     group_id: "int | None" = None) -> str:
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

    Returns '' if all pass, otherwise EVERY per-decision failure in one
    message. Caller must abort the commit when this returns non-empty —
    `commit_decisions` assumes verify passed.

    It used to stop at the first one, so a batch with three defects cost
    three wakes to learn three sentences the verifier already knew on
    the first pass (08-13 strategist report). The author cannot see
    these checks; the round trip is the only channel, and metering it
    one rejection at a time is the framework charging for its own
    silence. Cross-decision checks still run only on a clean set —
    their premise is that each decision is individually valid.
    """
    failures: "list[str]" = []
    for i, d in enumerate(decisions):
        err = verify_decision(d, conn, problem=problem,
                              group_id=group_id, workspace=workspace,
                              prior_decisions=decisions[:i])
        if err:
            failures.append(
                f"decision #{i}: {err}" if len(decisions) > 1 else err)
    if failures:
        if len(failures) == 1:
            return failures[0]
        return (f"{len(failures)} decisions were rejected — fix all of "
                f"them in the next batch:\n" + "\n".join(failures))

    # Cross-decision (owner rulings 2026-08-19, tightened same day): a
    # batch delegates SEVERAL groups or none — never exactly one. A
    # lone Delegate is the parent's own pipeline stage wearing a fresh
    # judgment loop (six such relays in the 4.5h after the
    # discussion-space wording landed, d7→d10). Counted per BATCH, not
    # against existing children — the earlier existing-fan allowance
    # let a group with one line already in flight keep shirking one
    # group at a time.
    n_delegates = sum(1 for d in decisions if d.kind == "Delegate")
    if n_delegates == 1:
        return (
            "A batch delegates several groups or none — never exactly "
            "one: a lone Delegate is your own next step wearing a new "
            "group. Split the burden into parallel lines and delegate "
            "them together (two groups may even race the same goal), "
            "or keep single-line work in your Roadmap's AHEAD — the "
            "next wake fires when this batch completes."
        )

    # Cross-decision: no ConfirmShelve(G) + goal-targeted Inject(
    # target=G) pair. The Inject force-reopens G (shelved /
    # pending_strategist_review / frozen → open in
    # `_commit_inject_redispatch`) and queues a retry; the
    # ConfirmShelve then flips G back to shelved. End state: G is
    # shelved but a Backward/Builder dispatch sits in the queue
    # targeting it. BFS would then try to dispatch a worker on a
    # shelved goal — undefined behaviour.
    confirm_targets: set[int] = {
        int(d.target_id) for d in decisions
        if d.kind == "ConfirmShelve" and d.target_id is not None
    }
    inject_bb_targets: set[int] = {
        int(d.target_id) for d in decisions
        if d.kind == "Inject" and d.target_id is not None
    }
    overlap_bb = confirm_targets & inject_bb_targets
    if overlap_bb:
        gid = next(iter(overlap_bb))
        return (
            f"batch contains both ConfirmShelve and a goal-targeted "
            f"Inject for goal {gid} — the Inject force-reopens the "
            f"target, the ConfirmShelve then shelves it; the queued "
            f"retry would dispatch on a shelved goal. Drop the "
            f"ConfirmShelve (the redispatch already keeps the goal "
            f"alive) or aim the Inject at a different goal."
        )

    # Cross-decision: ConfirmShelve(ancestor) + goal-targeted Inject(
    # target=descendant) is also rejected. ConfirmShelve flips the
    # ancestor to 'shelved' and dispatcher._set_goal_terminal_and_
    # propagate cascades that shelve down through strategy_subgoals to
    # every still-active descendant (dispatcher._cascade_shelve_
    # descendants). The cascade fires AFTER the Inject's auto-reopen
    # within the same batch, silently overriding it. The queued
    # Backward/Builder then dispatches on a goal whose status got flipped
    # back to shelved underneath it and moots immediately — observed BT
    # 2026-05-29 batch [Inject(g3298 sphere_paradoxical), ConfirmShelve(
    # g3296 main)]: Inject reopened g3298 at .475, ConfirmShelve cascade
    # re-shelved it at .486, Builder dispatched at .494 and the
    # goal_still_active check on entry returned False (status='shelved')
    # → moot, Strategist's rescue attempt dropped on the floor.
    if confirm_targets and inject_bb_targets:
        for ij_target in inject_bb_targets:
            if ij_target in confirm_targets:
                continue  # already caught above
            ancestors: set[int] = set()
            frontier = [ij_target]
            visited: set[int] = set()
            while frontier:
                next_frontier: list[int] = []
                for gid in frontier:
                    if gid in visited:
                        continue
                    visited.add(gid)
                    for r in conn.execute(
                        "SELECT s.goal_id FROM strategies s"
                        " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
                        " WHERE ss.subgoal_id = ?",
                        (gid,),
                    ).fetchall():
                        pid = int(r["goal_id"])
                        if pid not in ancestors:
                            ancestors.add(pid)
                            next_frontier.append(pid)
                frontier = next_frontier
            bad = ancestors & confirm_targets
            if bad:
                anc_id = next(iter(bad))
                return (
                    f"batch contains ConfirmShelve(goal {anc_id}) and "
                    f"Inject(target_goal_id={ij_target})"
                    f" where target is a descendant of the ConfirmShelve"
                    f" target through strategy_subgoals. ConfirmShelve"
                    f" cascades shelve to all descendants (dispatcher._"
                    f"cascade_shelve_descendants), which fires AFTER the"
                    f" Inject's auto-reopen and silently overrides it —"
                    f" the queued Backward/Builder dispatches on a now-"
                    f"shelved goal and moots immediately. Pick one"
                    f" intent: drop the ConfirmShelve and Inject(target="
                    f"{anc_id}, proof=\"…retry with the new tools at"
                    f" hand…\") to re-attack the whole subtree with the"
                    f" sub-rescue argument; OR keep the ConfirmShelve and"
                    f" drop this Inject (the descendant is acknowledged"
                    f" as cascade-dead)."
                )

    # Cross-decision: ConfirmShelve must be paired with at least one
    # ACTION decision in the same batch — Inject. EmitDirective is notes
    # only (not action); RequestUserAmend is the user-escalation channel
    # reserved for user-file/charter errors. Forces Strategist to
    # keep trying — articulating defeat without dispatching a fresh
    # attempt or redirecting focus is the lazy pattern this rule catches.
    #
    # SCOPE (2026-07-06, ConfirmShelve 終態): the pairing obligation
    # applies to FIRST-TIME shelves only (target not already 'shelved').
    # A ConfirmShelve re-confirming an already-shelved goal is the
    # "still dead" verdict — forcing an Inject onto it mints a fresh
    # reopen-promise (the shared batch_id), so the confirmation itself
    # re-armed the loop it was answering (feedback ×2: a superseded goal
    # re-fired after every batch, forever). A standalone re-confirm acks
    # the old promise and carries none (no Inject sibling = no promise),
    # permanently silencing the goal. Forcing is NOT weakened where it
    # matters: the root-blocked gate below still rejects ANY no-Inject
    # batch when nothing live is in flight, and an explicit
    # Inject(target=...) / G1 dedupe revival can always bring the goal
    # back.
    def _is_first_shelve(d) -> bool:
        g = db.get_goal(conn, d.target_id) if d.target_id is not None \
            else None
        return g is None or str(g["status"]) != "shelved"

    if any(d.kind == "ConfirmShelve" and _is_first_shelve(d)
           for d in decisions):
        action = sum(1 for d in decisions if d.kind == "Inject")
        if action == 0:
            return (
                "ConfirmShelve must be paired with at least one Inject "
                "decision in the same batch. EmitDirective alone (notes) "
                "and RequestUserAmend alone (user escalation) do not "
                "count — they don't dispatch a fresh attempt or redirect "
                "focus. Pair with one of:\n"
                "  - Inject(proof=..., no target) to mint the missing "
                "tool the shelved goal needed.\n"
                "  - Inject(target_goal_id=..., "
                "proof=...) to redispatch another goal (typically the "
                "parent of the shelved subgoal — its strategy will "
                "otherwise stay 'proposed' with an unfeasible subgoal), "
                "or to refocus on another goal worth attacking with a "
                "fresh hint.\n"
                "EmitDirective is fine as an EXTRA decision in the "
                "same batch to record learning, but it cannot be the "
                "sole sibling. If you genuinely have no fresh action "
                "to dispatch, the problem is upstream-blocked — "
                "escalate via RequestUserAmend in a separate Strategist "
                "call (which pauses dispatch via the awaiting_human "
                "gate)."
            )

    # Cross-decision: review-discharge (2026-07-11, b6 wake-pump). While
    # ANY goal sits in `pending_strategist_review`, the batch must contain
    # at least one decision TARGETING one of them (ConfirmShelve / Reopen /
    # Inject on that goal) — pending_review means "the
    # framework cannot progress without your verdict on THIS goal", and
    # `reconcile_stuck_states` re-wakes every tick until the set empties.
    # A batch that leaves every reviewed goal untouched (the EmitDirective-
    # only pattern) discharges nothing: the wake loop just paid an LLM
    # spawn for a note (301 spawns / 2.05M output tokens, b6 2026-07-10).
    # EmitDirective stays legal as an EXTRA sibling — what is rejected is
    # the notes-only batch, not the note. Exempt: Ingest (terminal exit —
    # queued Strategists are dropped after it) and RequestUserAmend (the
    # awaiting_human gate pauses the wake pump itself).
    # Scope (2026-07-12, periodic wakes outrank events): a routine
    # wake may now legally fire WHILE goals await review — discharging
    # them is the frontier wakes' job (the pending_review pressure keeps
    # re-arming until the set empties), not the periodic survey's.
    # Forcing the discharge here would bounce every periodic wake on a
    # busy tree (the parse-fail pump shape, e1ecc5c).
    pending_review_ids: set[int] = set()
    if trigger_kind != "routine":
        pending_review_ids = {
            int(r["id"]) for r in conn.execute(
                "SELECT id FROM goals WHERE problem = ?"
                "  AND status = 'pending_strategist_review'",
                (problem,),
            )
        }
    if pending_review_ids:
        exempt = any(d.kind in ("Ingest", "RequestUserAmend")
                     for d in decisions)
        addressed = any(
            d.target_id is not None and int(d.target_id) in pending_review_ids
            for d in decisions)
        if not exempt and not addressed:
            ids = ", ".join(f"g{i}" for i in sorted(pending_review_ids))
            return (
                f"review not discharged: goal(s) {ids} are in "
                f"pending_strategist_review — they wait on YOUR verdict, "
                f"and the framework re-wakes you every tick until you "
                f"give one. This batch targets none of them, so it "
                f"resolves nothing. Include at least one decision "
                f"targeting a reviewed goal:\n"
                f"  - ConfirmShelve(target_goal_id=...) — park it, "
                f"paired with an Inject per the shelve rule (build the "
                f"missing tool, or redirect focus elsewhere; a parked "
                f"goal stays revivable), OR\n"
                f"  - Inject(target_goal_id=...) — "
                f"keep it alive and re-attack it with a fresh brief "
                f"(force-reopens the goal); if you now suspect the "
                f"statement is false, Inject a mint of its negation "
                f"instead.\n"
                f"Other decisions may accompany these, but cannot be "
                f"the whole batch."
            )

    # Cross-decision: stall-advance (problem FSM design §3.1,
    # 2026-07-12 — the pure-NL re-confirm pump). Forced advance is THE
    # design philosophy; its old mechanical anchor was the root status,
    # so a rootless (pure-NL) problem had no enforcement and the gate
    # counted decision KINDS, not state deltas — a zero-delta batch
    # (re-confirm shelve / Noop / re-mark) passed as action. New
    # currency: `predicted_batch_delta` (transitions §2.3) — a stalled
    # wake with nothing live in flight must move ≥1 state or dispatch
    # ≥1 new piece of work, root or no root.
    if trigger_kind in BATCH_DONE_LIKE:
        try:
            # v35 — ask about THIS group's slice: a sibling group's work
            # is not this Strategist's excuse for a zero-delta batch.
            _stalled = (db.is_group_stalled(conn, problem, group_id)
                        if group_id is not None
                        else db.is_problem_stalled(conn, problem))
        except Exception:  # noqa: BLE001 — predicate must not break verify
            _stalled = False
        if _stalled and not db.has_live_inflight_inject(
                conn, problem, group_id=group_id):
            from ..state import transitions as _transitions
            if _transitions.predicted_batch_delta(conn, decisions) < 1:
                return (
                    "framework stalled and this batch changes nothing "
                    "(re-confirmed shelves, re-marks, Noop — all no-ops).\n"
                    "You are the researcher here, and this wall is yours "
                    "to break. Think deeply, be inventive, and explore "
                    "genuinely different possibilities — the breakthrough "
                    "comes from work only you can do: study the dead "
                    "attempts and name the assumption they share (that is "
                    "the dimension to vary); build the missing vocabulary "
                    "as Forward bricks; question your own DO-NOTs (a "
                    "verdict covers only the instantiation it cites); "
                    "test a false-looking statement; pick the experiment "
                    "whose outcome most changes your Thesis.\n"
                    "Commit the work as: `Inject` (a genuinely new angle) "
                    "/ `ConfirmShelve` (a live goal) paired with an "
                    "`Inject` / `MarkDeliverable` (a "
                    "PROVED forward node) then `Ingest`. "
                    "`RequestUserAmend` ONLY if a user file is factually "
                    "WRONG — difficulty or a missing API is work, not "
                    "wrongness. EmitDirective / Noop may accompany, "
                    "never alone."
                )

    # Cross-decision: if the root is in a state only Strategist can
    # unfreeze (`shelved` / `frozen` / `pending_strategist_review`),
    # AND this batch dispatches no fresh work (no Inject),
    # AND no LIVE Inject is still in flight from a prior Strategist call
    # — the daemon will idle-exit after this commit. BFS cannot dispatch
    # the root's subtree (`db.open_goals`'s alive seed is
    # `root ∪ detached ∪ alive-strategy descendants`; a non-actively-
    # dispatchable root contributes no seed). Reject.
    #
    # `pending_strategist_review` is included because that state means
    # "agent declined `shelve`, Strategist must decide" — the framework
    # cannot make progress without a Strategist verdict. A Noop on a
    # pending_review root is a logical contradiction (Strategist invoked
    # specifically to break the impasse, declines to act).
    #
    # `disproved` / `dead` roots intentionally NOT covered: those are
    # genuine dead ends (counterexample / wrong parent context) where
    # Strategist legitimately cannot recover; Noop is the right
    # acknowledgement.
    root_row = conn.execute(
        "SELECT id, status FROM goals"
        " WHERE problem = ? AND origin = 'root'",
        (problem,),
    ).fetchone()
    BLOCKED_STATES = ("shelved", "frozen", "pending_strategist_review")
    if root_row is not None and str(root_row["status"]) in BLOCKED_STATES:
        # v35 — `Delegate` dispatches work just as `Inject` does, and
        # the fresh-problem case the design leans on (first batch
        # delegates a burden instead of working the frozen root) is
        # EXACTLY this branch. Reading only 'Inject' here rejected it.
        #
        # `Ingest` counts too (owner ruling 2026-08-15). One that
        # reaches this cross-decision stage already passed its own
        # per-decision gate — and the top group's requires a PROVED
        # root, impossible here — so an Ingest under a parked root is
        # always a sub-group delivery, whose terminal write wakes the
        # parent (groups.set_status): the daemon does not idle. Before
        # this, no group ever exited marks+Ingest-only: 13 of 14
        # delivered groups' exit batches carried a companion Inject —
        # claude-era groups paid the tax in spare real bricks, codex's
        # settled micro-groups had to invent compliance experiments
        # (one mis-aimed root attack among them). Keep the check LOCAL:
        # Ingest must NOT join BATCH_DECISION_KINDS, which also feeds
        # the >=1-experiment rule and batch_id dispatch.
        has_action = any(
            d.kind in db.BATCH_DECISION_KINDS or d.kind == "Ingest"
            for d in decisions)
        if not has_action:
            # A NULL-outcome Inject counts as in-flight ONLY if it is LIVE
            # — its produced goal is NOT parked. A `shelved`-produced inject
            # stays NULL forever (shelved no longer settles — see
            # db.propagate_inject_outcome_from_goal), so the old blanket
            # "any NULL-outcome batch row" test wrongly read it as in-flight
            # and ALLOWED a Noop here, while T4 (db.is_problem_stalled) read
            # the same problem as stalled and re-fired the Strategist → Noop
            # → re-fire LIVELOCK (the P13 4284 spin). `has_live_inflight_
            # inject` excludes shelved-produced injects so the two agree: no
            # live inject ⇒ reject Noop ⇒ force a real action. It is BROADER
            # than the stall predicate's active-check on purpose (a Forward
            # inject whose worker has not yet registered its lemma is LIVE
            # here — we have no `running`-set visibility — so the Strategist
            # may Noop and wait instead of injecting overlapping work).
            has_live_inflight = db.has_live_inflight_inject(
                conn, problem, group_id=group_id)
            if not has_live_inflight:
                rstat = str(root_row["status"])
                rid = int(root_row["id"])
                hint_for_pending = (
                    " Pending-review state means the last Backward agent "
                    "declined `shelve` on the root — you were invoked "
                    "specifically to break the impasse. Noop here is a "
                    "logical contradiction." if rstat == "pending_strategist_review"
                    else ""
                )
                return (
                    f"Root (goal_id={rid}) is {rstat!r} and nothing in "
                    f"the framework will progress without your action: "
                    f"no live in-flight Inject (any prior inject's brick is "
                    f"parked/shelved, not producing), and this batch "
                    f"neither dispatches work nor delivers. BFS cannot "
                    f"dispatch from a {rstat!r} root, so a "
                    f"Noop/EmitDirective-only batch leaves the daemon "
                    f"idle.{hint_for_pending}\n"
                    f"Ways forward:\n"
                    f"  - your charter is settled → `MarkDeliverable` + "
                    f"`Ingest`: a delivering exit is progress (it wakes "
                    f"the level above), OR\n"
                    f"  - `Inject(proof=...)` / `Delegate(...)` to "
                    f"dispatch the work still missing (root stays "
                    f"{rstat!r}; inject_batch_done will re-fire you), "
                    f"OR\n"
                    f"  - the root subtree is yours and the toolkit is "
                    f"ready → `Inject(target_goal_id={rid}, proof=...)` "
                    f"re-engages BFS on it, OR\n"
                    f"  - `RequestUserAmend(...)` ONLY if a user file is "
                    f"factually wrong."
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
    `enqueued_forward`: True iff the commit emitted >= 1 mint Inject
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
                         inject_batch_id: str | None = None,
                         step_index: int = 0,
                         batch_size: int = 1,
                         group_id: "int | None" = None) -> CommitOutcome:
    """Commit one Strategist Inject decision. Dispatches to the
    pipeline-specific helper.

    Batch semantics (unified across pipeline kinds): every Inject row
    carries a `batch_id`. The framework fires Strategist with
    `inject_batch_done` once every decision in the batch has reached
    a terminal outcome.

      - Forward outcome fills when the produced lemma reaches a
        terminal goal status (proved / shelved / disproved / dead).
      - Backward outcome fills when the produced strategy reaches
        a terminal status (succeeded / dead / superseded).
      - Builder outcome fills when the target goal reaches terminal
        (Builder writes the proof directly into the goal's stub).

    Multi-decision callers pass `inject_batch_id` to share one UUID
    across the whole batch — including across pipeline kinds — so a
    single wake-up coalesces all completions.
    """
    # Shape-derived (update_plan_2026_07 #1): no target → mint a new
    # brick; target present → redispatch the goal to the Formalizer.
    if decision.target_id is None:
        return _commit_inject_forward(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, batch_id_override=inject_batch_id,
            step_index=step_index, batch_size=batch_size,
            group_id=group_id)
    return _commit_inject_redispatch(
        decision, conn, problem=problem, tick=tick,
        trigger_kind=trigger_kind, pipeline="Formalizer",
        batch_id_override=inject_batch_id,
        step_index=step_index, batch_size=batch_size,
        group_id=group_id)


def _commit_inject_forward(decision: Decision, conn: sqlite3.Connection,
                           *, problem: str, tick: int,
                           trigger_kind: str,
                           batch_id_override: str | None = None,
                           step_index: int = 0,
                           batch_size: int = 1,
                           group_id: "int | None" = None) -> CommitOutcome:
    """Mint variant — 1 brief → 1 row + 1 Formalizer enqueue
    (target_kind=Problem).

    `batch_id_override` lets a multi-decision call share one batch_id
    across all N mint Inject decisions so cascade fires a single
    `inject_batch_done` once every produced lemma terminates. Solo
    (single-decision) calls leave it None and get a fresh batch_id.
    """
    brief = decision.brief.strip()
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()
    row_payload = {
        "pipeline": "Formalizer",
        "step_index": step_index,
        "batch_size": batch_size,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief,"
        " reason, payload, batch_id, outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', ?, NULL, ?, ?, ?, ?, NULL, ?, ?)",
        (problem, tick, trigger_kind, group_id, brief,
         decision.reason, json.dumps(row_payload, ensure_ascii=False),
         batch_id, ts, ts),
    )
    row_id = int(cur.lastrowid)
    db.enqueue(
        conn, kind="Formalizer", target_id=problem,
        target_kind="Problem", priority=10,
        decision_id=row_id, problem=problem,
    )
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
                              pipeline: str,
                              batch_id_override: str | None = None,
                              step_index: int = 0,
                              batch_size: int = 1,
                              group_id: "int | None" = None,
                              ) -> CommitOutcome:
    """Backward / Builder variant — 1 row + 1 enqueue on target goal.

    `brief` carries the agent's hint for the redispatch.

    Every Inject row carries a `batch_id` (a fresh UUID for solo
    commits, shared across the batch when multiple decisions commit
    together) so the framework can fire `inject_batch_done` once the
    batch's last decision reaches terminal — mirroring Forward.

    `produced_goal_id = target_id`: lets the goal-side propagation
    fill outcome when the target reaches a terminal goal status
    (Builder's intent is to prove the goal directly, so this is the
    canonical completion signal for Builder). For Backward the
    worker additionally sets `produced_strategy_id` after reserving
    its strategy id; outcome fills via whichever path resolves first
    (idempotent via the `outcome IS NULL` guard), so a Backward
    Inject whose injected strategy dies via cascade still surfaces a
    wake-up even while the target goal stays 'attempting' under a
    sibling.
    """
    target_id = int(decision.target_id)
    brief = decision.brief.strip()
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()
    row_payload = {
        "pipeline": pipeline,
        "step_index": step_index,
        "batch_size": batch_size,
        "target_goal_id": target_id,
    }
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief,"
        " reason, payload, batch_id, produced_goal_id, produced_kind,"
        " outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, 'Inject', ?, ?, ?, ?, ?, ?, ?, 'redispatch',"
        " NULL, ?, ?)",
        (problem, tick, trigger_kind, group_id, target_id,
         brief, decision.reason,
         json.dumps(row_payload, ensure_ascii=False),
         batch_id, target_id, ts, ts),
    )
    row_id = int(cur.lastrowid)

    # Force-reopen target so BFS / inject dispatch can run on it.
    # Auto-detach if the upward chain has died — same path Strategist
    # Reopen takes. `dead` is a hard terminal already rejected by
    # verify_decision; this list intentionally excludes it. `disproved`
    # is IN it (2026-08-18): an Inject on one is the revival route for
    # a claimed-counterexample park.
    g = db.get_goal(conn, target_id)
    if g and str(g["status"]) in ("shelved", "pending_strategist_review",
                                   "frozen", "disproved"):
        transitions.apply_goal_transition(
            conn, target_id, "open", event="strategist_reopen")
        if _dispatcher._has_dead_strategy_in_chain(conn, target_id):
            db.set_goal_detached(conn, target_id, True)
        # Un-stall the upward chain (Phase 11): a parent strategy PARKED
        # as 'stalled' because this goal was its last settled sub-goal
        # returns to 'proposed', so the alive-DAG conducts through it again
        # and BFS can reach the just-reopened goal — otherwise it stays
        # orphaned. ('proposed' is non-terminal → no inject-outcome
        # re-propagation; the prior 'failed:stalled' record stands, the
        # fresh redispatch Inject below tracks the revived attempt.)
        for s in conn.execute(
            "SELECT s.id FROM strategies s"
            " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
            " WHERE ss.subgoal_id = ? AND s.status = 'stalled'",
            (target_id,),
        ).fetchall():
            transitions.apply_strategy_transition(
                conn, int(s["id"]), "proposed", event="strategist_unstall")

    # entry_kind pinning retired with the Formalizer merge: bfs_refill
    # and Inject now enqueue the SAME kind, so the in_flight(gid, kind)
    # guard structurally prevents the parallel-pipeline race the old
    # pin worked around (LU lu_step_assembly 2026-05-28).
    db.enqueue(
        conn, kind=pipeline, target_id=str(target_id),
        target_kind="Goal", priority=10,
        decision_id=row_id, problem=problem,
    )
    conn.commit()
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def _commit_delegate(decision: Decision, conn: sqlite3.Connection,
                     *, problem: str, tick: int, trigger_kind: str,
                     group_id: "int | None",
                     batch_id_override: str | None = None,
                     step_index: int = 0,
                     batch_size: int = 1) -> CommitOutcome:
    """Open a sub-group and hand it the charter (v35).

    The row rides the same batch as this wake's Injects, and its
    `produced_group_id` is the batch's THIRD artifact form: the outcome
    fills when the group reaches a terminal status, so a batch that
    dispatched both a Formalizer and a group wakes the parent only once
    BOTH are done.

    Two shapes:
      * no target — the main one. A burden delegated while writing the
        Proof; the group starts from prose and mints its own bricks,
        exactly like a pure-NL problem.
      * `target_goal_id` — the rescue shape. The goal becomes the
        group's ANCHOR and goes `attempting`: not dispatchable by BFS,
        but alive, which is what lets the parent stay quiet (§5 of the
        design doc).

    Unlike an Inject, no worker is enqueued — the group's executor is
    its own Strategist seat. That seat IS queued here rather than left
    to the routine clock: a fresh group's clock is NULL, which the T1
    selector reads as "due one full interval after daemon start", and a
    just-delegated burden should not wait up to two hours to begin.
    """
    parent = _authoring_group(conn, problem, group_id)
    if parent is None:                       # verify already rejected this
        raise RuntimeError(f"Delegate on {problem!r} has no authoring group")
    charter = str(decision.brief).strip()
    target = (int(decision.target_id)
              if decision.target_id is not None else None)
    batch_id = batch_id_override or uuid.uuid4().hex
    ts = db.now()

    # Copy-on-open (2026-08-11): conventions no longer walk the ancestor
    # chain, so this snapshot is the only way a footgun learned up here
    # reaches a group opened now. Taken at open time and never refreshed
    # — the child owns the subject from its first `## Conventions` on.
    from ..state import programme as _programme
    new_gid = _groups.open_group(
        conn, problem=problem, parent_group_id=int(parent["id"]),
        charter=charter, anchor_goal_id=target,
        conventions_seed=_programme.conventions_for_group(
            conn, problem, int(parent["id"])))
    row_payload = {
        "step_index": step_index,
        "batch_size": batch_size,
        "group_id": new_gid,
    }
    if target is not None:
        row_payload["target_goal_id"] = target
    # Guidance hand-off (2026-08-19 reshape): lives on THIS audit row;
    # the child's context reads it back through `groups.opened_by` —
    # no schema change, and it never touches the judged charter.
    if decision.payload.get("brief"):
        row_payload["brief"] = str(decision.payload["brief"])
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief, reason,"
        " payload, batch_id, produced_group_id, produced_kind, outcome,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, 'Delegate', ?, ?, ?, ?, ?, ?, ?, 'group',"
        " NULL, ?, ?)",
        (problem, tick, trigger_kind, int(parent["id"]), target, charter,
         decision.reason, json.dumps(row_payload, ensure_ascii=False),
         batch_id, new_gid, ts, ts),
    )
    row_id = int(cur.lastrowid)
    conn.execute("UPDATE groups SET opened_by = ? WHERE id = ?",
                 (row_id, new_gid))
    if target is not None:
        # `attempting` — alive (so the parent's wait is legal) but not
        # dispatchable by BFS. See the status table in the design doc:
        # `frozen` and `shelved` are both PARKED and would let T4 wake
        # the parent on every tick.
        g = db.get_goal(conn, target)
        if g is not None and str(g["status"]) != "attempting":
            transitions.apply_goal_transition(
                conn, target, "attempting", event="delegate_anchor")
    _dispatcher._enqueue_strategist(conn, new_gid, problem, priority=10)
    conn.commit()
    print(f"[delegate] group {new_gid} opened under {parent['id']} "
          f"({problem}): {charter[:80]}", flush=True)
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
        batch_id=batch_id,
        batch_decision_row_ids=[row_id],
    )


def _commit_return_to_parent(decision: Decision, conn: sqlite3.Connection,
                             *, problem: str, tick: int,
                             trigger_kind: str,
                             group_id: "int | None") -> CommitOutcome:
    """Hand the charter back up (v35).

    Setting the group's status to 'returned' is what fills the parent's
    `Delegate` outcome and completes its batch — the parent is woken by
    the ordinary batch-done relay, not by anything special here.

    The anchor of a rescue-shape group goes back to `shelved`: parked,
    revivable, and its cascade parks the failed subtree with it. The
    parent decides what happens next; that is the whole point of handing
    it back rather than deciding alone.
    """
    me = _authoring_group(conn, problem, group_id)
    if me is None or _groups.is_top(me):     # verify already rejected this
        raise RuntimeError(
            f"ReturnToParent on {problem!r} has no parent group")
    flavour = str(decision.payload.get("flavour"))
    ts = db.now()
    payload = dict(decision.payload)
    payload["group_id"] = int(me["id"])
    payload["charter"] = str(me["charter"])
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, reason,"
        " payload, produced_group_id, outcome, outcome_detail,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, 'ReturnToParent', ?, ?, ?, ?, ?, 'committed',"
        " ?, ?, ?)",
        (problem, tick, trigger_kind, int(me["id"]),
         decision.target_id, decision.reason,
         json.dumps(payload, ensure_ascii=False), int(me["id"]),
         flavour, ts, ts),
    )
    row_id = int(cur.lastrowid)
    anchor = me["anchor_goal_id"]
    if anchor is not None:
        g = db.get_goal(conn, int(anchor))
        if g is not None and str(g["status"]) in (
                "open", "attempting", "pending_strategist_review", "frozen"):
            transitions._set_goal_terminal_and_propagate(
                conn, int(anchor), "shelved")
            transitions._propagate_shelve(conn, int(anchor))
    # Terminal status LAST: it fills the parent's Delegate outcome and
    # may fire the batch-done wake, so everything the parent will read
    # must already be written.
    _groups.set_status(conn, int(me["id"]), "returned",
                       event="group_returned")
    if flavour == "refuted":
        # A refutation cannot wait for the batch. `refuted` means a step
        # of the PARENT's Proof is now kernel-false, so every sibling
        # still running under that Proof is working on an invalidated
        # premise — and siblings dispatched in the same batch keep the
        # batch open, so the ordinary relay would leave the parent
        # asleep for up to a full routine interval. Same reasoning, and
        # the same priority band, as a `pending_strategist_review`
        # escalation. Not pumpable: every refutation costs a
        # kernel-checked negation brick.
        parent_id = int(me["parent_group_id"])
        if not db.is_in_queue(conn, target_id=str(parent_id),
                              kind="Strategist"):
            db.enqueue(conn, kind="Strategist", target_id=str(parent_id),
                       target_kind="Group", priority=20, problem=problem)
            print(f"[return] refutation — woke parent group {parent_id} "
                  f"immediately (batch not waited on)", flush=True)
    conn.commit()
    print(f"[return] group {me['id']} returned to {me['parent_group_id']} "
          f"({problem}, {flavour}): {str(decision.reason or '')[:80]}",
          flush=True)
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
    )


def _commit_close_group(decision: Decision, conn: sqlite3.Connection,
                        *, problem: str, tick: int, trigger_kind: str,
                        group_id: "int | None") -> CommitOutcome:
    """Retire a child group (v35). The reverse of `Delegate`.

    A parent's Programme is alive: its route changes, and a burden it
    delegated three revisions ago can stop mattering. Without this the
    only way to stop that group is to wait for it to hit its own wall
    and hand the charter back — the tokens in between buy nothing.

    Reaching `closed` fills the opening `Delegate` outcome, so the
    parent's batch completes through the ordinary relay. The child's
    seat stops on its own: `groups_needing_t1` and `groups_stalled` both
    select `status = 'active'` only. Workers already in flight finish
    and write; nothing is torn out from under them.
    """
    me = _authoring_group(conn, problem, group_id)
    target = int(decision.payload["target_group_id"])
    kid = _groups.get(conn, target)
    if me is None or kid is None:            # verify already rejected this
        raise RuntimeError(f"CloseGroup({target}) on {problem!r} is invalid")
    ts = db.now()
    payload = dict(decision.payload)
    payload["charter"] = str(kid["charter"])
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, reason, payload,"
        " produced_group_id, outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, 'CloseGroup', ?, ?, ?, ?, 'committed', ?, ?)",
        (problem, tick, trigger_kind, int(me["id"]), decision.reason,
         json.dumps(payload, ensure_ascii=False), target, ts, ts),
    )
    row_id = int(cur.lastrowid)
    # The anchor-shelve lives inside `set_status` now (one spelling for
    # the direct close, the ancestor cascade and the startup sweep).
    _groups.set_status(conn, target, "closed", event="group_closed")
    conn.commit()
    print(f"[close] group {target} retired by {me['id']} ({problem}): "
          f"{str(decision.reason or '')[:80]}", flush=True)
    return CommitOutcome(
        decision_row_id=row_id,
        enqueued_forward=False,
        final_outcome="committed",
    )


def commit_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str, tick: int, trigger_kind: str,
                     workspace: Path,
                     group_id: "int | None" = None,
                     ) -> list[CommitOutcome]:
    """Execute a multi-decision batch in declared order.

    Caller must have already passed `verify_decisions`. All decisions
    commit; per-kind side effects fire individually. The transaction
    boundary is per-decision (each per-kind helper calls
    `conn.commit()`); a mid-batch raise leaves earlier rows committed,
    which mirrors the existing single-decision contract — verify is
    expected to catch every user-error case, so any raise here
    indicates a framework bug to investigate, not graceful recovery
    territory.

    Inject batching is unified across pipeline kinds: every Inject
    decision in `decisions` shares one `batch_id`, so the cascade
    fires `inject_batch_done` exactly once — when the LAST of the
    Forward / Backward / Builder injects reaches terminal. Each kind
    has its own completion signal (see `_commit_inject_batch`).

    Returns one CommitOutcome per decision (same order).
    """
    # A retired charter accepts no new batch — the any-caller backstop
    # behind `run_strategist`'s round-boundary and pre-commit doors.
    # Raising (not dropping) is deliberate: every sanctioned path checks
    # first, so reaching here retired means an unguarded caller.
    _retired = _group_retired_status(conn, problem, group_id)
    if _retired is not None:
        raise ValueError(
            f"commit_decisions: group {group_id} is {_retired} — a "
            "retired charter accepts no new batch (check "
            "_group_retired_status before committing)")
    # v35 — stamp every row this batch writes with its AUTHORING group.
    # Done as one post-pass keyed on "rows that did not exist before",
    # rather than threading the id through a dozen per-kind INSERTs: a
    # new decision kind then cannot be added and silently forget it, and
    # rows written by nested helpers are covered too.
    _before = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM strategist_decisions"
    ).fetchone()[0]
    inject_batch_id: str | None = None
    # v35 — `Delegate` counts: a batch whose only experiment is a delegated
    # burden must still get a batch_id, or nothing ever wakes the parent
    # when the child group finishes. `db.BATCH_DECISION_KINDS` is the one
    # definition of "rides the batch cycle".
    n_inject = sum(1 for d in decisions
                   if d.kind in db.BATCH_DECISION_KINDS)
    if n_inject:
        inject_batch_id = uuid.uuid4().hex
    # Real per-step indices: the audit payload's step_index was hardcoded
    # 0 for every row, so `## Completed Inject batches` labelled all
    # steps "step 0" and the Strategist couldn't line outcomes up with
    # its briefs (feedback 2026-07-04, repeated).
    out: list[CommitOutcome] = []
    step = 0
    for d in decisions:
        idx = step
        if d.kind in db.BATCH_DECISION_KINDS:
            step += 1
        out.append(_commit_one(
            d, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, workspace=workspace,
            inject_batch_id=inject_batch_id,
            inject_step_index=idx, inject_batch_size=n_inject,
            group_id=group_id))
    # Wake-clock touch — ONE point for the whole batch (task #119).
    # When each per-kind path touched last_strategist_at itself, the
    # early-return paths (Inject / FetchPaper) never
    # learned about the ROUTINE clock: a pure-Inject routine batch left
    # last_routine_at NULL, T1 read "never routine'd", and a fresh
    # routine wake was enqueued the instant the previous one finished —
    # a strategist pump (b6_1 leg 6, 2026-07-25). A mid-batch raise
    # skips the touch: an un-acknowledged batch must not advance either
    # clock.
    from ..state import groups as _groups
    gid = group_id if group_id is not None else \
        _groups.ensure_top_group(conn, problem)
    # Every per-kind INSERT writes `group_id` itself. This is the
    # exhaustiveness CHECK, not the writer: a blind range UPDATE over
    # "rows newer than my snapshot" is wrong the moment two groups of
    # the same problem commit concurrently — which is exactly the
    # concurrency the per-group seat just bought — because each would
    # stamp the other's rows and every downstream reading (ownership,
    # stall, deliverables) would follow the wrong group. Fail loud
    # instead: a decision kind that forgets is a framework bug.
    unstamped = conn.execute(
        "SELECT COUNT(*) FROM strategist_decisions"
        " WHERE id > ? AND problem = ? AND group_id IS NULL",
        (int(_before), problem)).fetchone()[0]
    if unstamped:
        raise RuntimeError(
            f"{unstamped} decision row(s) committed without a group_id "
            f"on {problem!r} — a per-kind INSERT missed it")
    # The wake's clocks advance here and nowhere else. `touch_clocks` was
    # the admin turn's opt-out — an admin commit that advanced them would
    # let a wake whose math half failed read as "strategist ran",
    # starving the retry pressure. With one turn there is no half to
    # fail separately, so the flag went with the split (2026-08-11).
    db.update_problem_last_strategist_at(conn, problem)
    _groups.touch_strategist(conn, int(gid),
                             routine=(trigger_kind == "routine"))
    if trigger_kind == "routine":
        db.update_problem_last_routine_at(conn, problem)
    conn.commit()
    return out


def commit_decision(decision: Decision, conn: sqlite3.Connection,
                    *, problem: str, tick: int, trigger_kind: str,
                    workspace: Path,
                    group_id: "int | None" = None) -> CommitOutcome:
    """Single-decision wrapper around `commit_decisions`. Preserved
    so existing callers (single-decision tests, anyone hand-driving
    one decision) keep their CommitOutcome-returning contract.
    """
    return commit_decisions(
        [decision], conn, problem=problem, tick=tick,
        trigger_kind=trigger_kind, workspace=workspace,
        group_id=group_id,
    )[0]


def _commit_ingest(conn: sqlite3.Connection, *, problem: str,
                   workspace: Path,
                   group_id: "int | None" = None) -> None:
    """Execute a Strategist `Ingest` decision's side effect (anchor+claim
    Phase 4).

    The sign-off pause and the Library decision are separate axes
    (2026-07-18 gate retirement): `signoff: false` (machine setting,
    benchmark adapters only) × `library.require_signoff` config decide
    pause-vs-direct; `library:` decides harvest only. A paused problem
    sets `ingest_signoff_pending` and waits for `asterism
    approve-ingest` (→ enqueue Librarian iff library) or `reject-ingest`
    (→ back to proving); direct ingest harvests iff the standing
    `library` flag. The old coupling (library:false silently skipped
    the human gate) let any opt-out producer bypass sign-off.

    Phase 6 — Ingest is the problem's ONLY terminal: this commit stamps
    `problems.ingested_at`, which drives the T1/T4 liveness predicates,
    the stale-row drop, the Librarian selfstart eligibility and the
    daemon exit check. `reject-ingest` and the rollback auto-revoke
    clear the stamp (back to the live path). The old root-proved-auto
    Librarian trigger in `verify.root_integrity_gate` is retired —
    harvest is strictly Ingest-driven now."""
    from ..core import config as _config
    from ..state import intent as _intent
    # v35 — a SUB-group's Ingest is a DELIVERY UPWARD, not a terminal.
    # Everything below this branch is problem-terminal semantics: the
    # human sign-off pause, the Library harvest, the regression
    # milestone, the review snapshot, `problems.ingested_at` and the
    # problem FSM edge. A group handing its charter back up must touch
    # none of them — it would pause the whole problem for a human, or
    # publish a snapshot of a tree that is still being built.
    #
    # What it does instead is one write: reaching 'delivered' fills the
    # parent's `Delegate` outcome, which completes the parent's batch
    # and wakes it through the ordinary relay. The bricks this group
    # marked are then the parent's to cite.
    me = _authoring_group(conn, problem, group_id)
    if me is not None and not _groups.is_top(me):
        _groups.set_status(conn, int(me["id"]), "delivered",
                           event="group_delivered")
        conn.commit()
        marked = db.deliverables(conn, problem=problem,
                                 group_id=int(me["id"]))
        print(f"[strategist] Ingest({problem}): group {me['id']} "
              f"delivered {len(marked)} brick(s) to group "
              f"{me['parent_group_id']}", flush=True)
        return
    # Tripwire, not a gate (operator ruling 2026-08-02 — log only, the
    # human is not asked). `ingested_at` is what `groups_stalled` and
    # `is_group_stalled` filter on, so the instant the TOP group Ingests,
    # every still-`active` sub-group stops being woken: no T4, no error,
    # nothing. Whether the right rule is wait / auto-close / refuse is a
    # design question deliberately left open until a real group tree has
    # run — but the framework must not do it in silence, and this line is
    # the evidence that decision will be made from.
    if me is not None:
        live = _groups.children(conn, int(me["id"]), active_only=True)
        if live:
            print(f"[ingest-orphans] {problem}: top-group Ingest with "
                  f"{len(live)} sub-group(s) still active "
                  f"({', '.join(str(g['id']) for g in live)}) — they stop "
                  f"being woken once `ingested_at` is stamped",
                  flush=True)
    # Decide the sign-off gate BEFORE publishing the terminal stamp.
    # `ingested_at` + a clear flag is what the Librarian selfstart path
    # reads as "approved, go" — so the flag must land in the same
    # transaction as the stamp. The pre-fix order stamped first and set
    # the flag AFTER store_review_snapshot, whose gateway warm-up is a
    # 30s+ window on a cold/stale gateway; the dispatcher tick inside
    # that window auto-started the harvest chain past the human gate
    # (observed 2026-07-06, Logic.toy_list_reverse: dedupe→migrate ran
    # before "paused for human sign-off" printed).
    harvest = True
    signoff_optout = False
    harvest_skip_msg = ""
    pintent = _intent.read(conn, problem)
    if pintent is None:
        # Unreadable intent: no harvest, but DO pause — failing into
        # the human gate is the safe direction.
        harvest = False
        harvest_skip_msg = (f"[strategist] Ingest({problem}): intent "
                            f"unreadable (no problems row); no harvest")
    else:
        signoff_optout = not pintent.signoff
    if harvest and not pintent.library:
        harvest = False
        harvest_skip_msg = (f"[strategist] Ingest({problem}): "
                            f"library:false — opted out of Library; "
                            f"no harvest")
    require_signoff = (not signoff_optout) and _as_bool(_config.get(
        "library.require_signoff", default=True, workspace=workspace))

    # Terminal stamp + gate flag: one atomic publication. Even when the
    # problem opts out of harvest the Strategist's terminal judgment
    # stands; only the harvest side-effects vary.
    db.set_problem_ingested(conn, problem)
    from ..state import transitions as _transitions
    if require_signoff:
        db.set_ingest_signoff_pending(conn, problem, True)
        _transitions.apply_problem_transition(
            conn, problem, "ingest_signoff", event="ingest_committed")
    else:
        _transitions.apply_problem_transition(
            conn, problem, "ingested", event="ingest_direct")
    conn.commit()

    # Slow best-effort work AFTER the gate is closed.
    # Regression manifest (task #8): the milestone auto-records itself —
    # tracked JSONL, best-effort, never blocks the Ingest.
    from ..state import regress as _regress
    # Auditability (frontmatter dissolve): the effective machine
    # settings ride the milestone line — the axiom-whitelist history
    # stays reconstructible from git even though the yaml stopped
    # changing. Best-effort like the rest of the record.
    settings_snapshot = None
    if pintent is not None:
        settings_snapshot = {
            "axioms_whitelist": _intent.effective_axioms(
                pintent, problem=problem),
            "forbidden_lemmas": list(pintent.forbidden_lemmas),
            "library": bool(pintent.library),
            "signoff": bool(pintent.signoff),
        }
    _regress.record_terminal(
        workspace, problem=problem, terminal="ingested",
        deliverables=len(db.deliverables(conn, problem)),
        settings=settings_snapshot)
    # Review snapshot (frontend charter §5-4): compute the anchor+claim
    # closure NOW, while the gateway is warm from the proving run — the
    # sign-off surfaces (CLI default, serve API) then read the stored
    # JSON instead of paying a 30s+ cold gateway per view. Best-effort:
    # a failure degrades readers to live compute, never blocks Ingest.
    from ..quality import review as _review
    _review.store_review_snapshot(conn, workspace, problem)

    if require_signoff:
        # The Library decision is (re)made at the signature; the current
        # flag is just the standing default, so a false flag is worth a
        # note but never skips the pause.
        if not harvest:
            print(harvest_skip_msg, flush=True)
        print(f"[strategist] Ingest({problem}): paused for human sign-off — "
              f"`asterism approve-ingest {problem}` to harvest, "
              f"`asterism reject-ingest {problem} --reason ...` to keep "
              f"proving", flush=True)
    elif not harvest:
        print(harvest_skip_msg, flush=True)
    else:
        db.enqueue(conn, kind="Librarian", target_id=problem,
                   target_kind="Problem", priority=0, problem=problem)
        print(f"[strategist] Ingest({problem}): direct ingest — enqueued "
              f"Librarian", flush=True)


def _commit_one(decision: Decision, conn: sqlite3.Connection,
                *, problem: str, tick: int, trigger_kind: str,
                workspace: Path,
                inject_batch_id: str | None,
                inject_step_index: int = 0,
                inject_batch_size: int = 1,
                group_id: "int | None" = None) -> CommitOutcome:
    """Execute one decision's side effects + INSERT audit row.

    Caller must have already passed `verify_decision`. This is the
    write-path; errors here indicate a bug (or a race with another
    Strategist commit), not user error. `inject_batch_id` is
    threaded through to `_commit_inject_batch` so every Inject
    decision in the same `commit_decisions` call shares one batch
    UUID (Forward / Backward / Builder mixed; see `commit_decisions`).
    """
    k = decision.kind
    outcome = "committed"
    enqueued_forward = False
    if group_id is None:
        group_id = _groups.ensure_top_group(conn, problem)

    if k == "Inject":
        return _commit_inject_batch(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind,
            inject_batch_id=inject_batch_id,
            step_index=inject_step_index,
            batch_size=inject_batch_size,
            group_id=group_id,
        )

    if k == "Delegate":
        return _commit_delegate(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, group_id=group_id,
            batch_id_override=inject_batch_id,
            step_index=inject_step_index,
            batch_size=inject_batch_size,
        )

    if k == "CloseGroup":
        return _commit_close_group(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, group_id=group_id,
        )

    if k == "ReturnToParent":
        return _commit_return_to_parent(
            decision, conn, problem=problem, tick=tick,
            trigger_kind=trigger_kind, group_id=group_id,
        )

    if k == "Noop":
        # No side effect beyond the audit row + last_strategist_at.
        pass

    elif k == "EmitDirective":
        # verify_decision rejects the retired kind before commit; reaching
        # here means a verify bypass — fail loudly, never write.
        raise RuntimeError(
            "EmitDirective is retired (Conventions section) but reached "
            "commit — a verify path let it through")

    elif k == "ConfirmShelve":
        gid = int(decision.target_id)  # type: ignore[arg-type]
        # No-op guard (BT 2026-05-29 g3380): a ConfirmShelve on a goal
        # that is already a hard terminal (proved / disproved / dead) is
        # silently ignored — it does NOT bounce the batch back to the
        # Strategist for re-issue. The Strategist sometimes ConfirmShelves
        # a proved-but-superseded orphan (it has no clean "retire orphan"
        # verb); shelving it would regress a completed proof and break
        # `proved ⟺ subs proved`. The rest of the batch (paired Injects,
        # directives) commits normally. The dispatcher's
        # _set_goal_terminal_and_propagate carries the same guard as a
        # class-level backstop, but short-circuiting here also skips the
        # _propagate_shelve cascade and keeps the decision's outcome benign.
        _g = db.get_goal(conn, gid)
        if _g is not None and \
                str(_g["status"]) in transitions.GOAL_HARD_TERMINALS:
            print(f"[strategist] ConfirmShelve(g{gid}) no-op — goal already "
                  f"{_g['status']!r}; not downgrading a terminal goal",
                  flush=True)
        else:
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

    elif k == "MarkDeliverable":
        # Synchronous: flag the Forward node top-level. `asterism review`
        # then computes + presents its anchor closure for human opt-out
        # review. Falls through to the shared audit-row INSERT (outcome
        # 'success').
        db.mark_deliverable(conn, int(decision.target_id))  # type: ignore[arg-type]


    elif k == "Ingest":
        # Terminal judgment → pause for human sign-off (unless the
        # problem's `signoff: false` machine setting or config opts
        # into direct ingest); harvest to Library iff `library:`.
        # Falls through to the audit INSERT.
        _commit_ingest(conn, problem=problem, workspace=workspace,
                       group_id=group_id)

    elif k == "RequestUserAmend":
        # Atomic three-step: tmp write -> INSERT row -> rename
        # (see docs/archive/design/phase2/pipelines.md §2.5).
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
    #
    # `batch_id` is shared with the batch's Inject rows: when a
    # ConfirmShelve / Reopen / etc. ships in the same JSON decision
    # array as one or more Inject(s), it inherits the same UUID. The
    # `_section_pending_reopens` Context.md section uses this link to
    # surface a shelved goal ONLY when the Strategist-promised batch
    # of follow-up Injects has completed — instead of re-surfacing
    # the goal on every unrelated inject_batch_done wake (brouwer
    # 2026-05-22: g2771 ConfirmShelve'd 4× because Context.md kept
    # listing it on every wake regardless of who was woken). For
    # solo non-Inject batches (no paired Inject), inject_batch_id is
    # None and the column stays NULL, matching the pre-fix shape.
    payload_for_audit = {
        k: v for k, v in decision.payload.items()
        if not str(k).startswith("__")
    }
    # DB outcome ≠ caller signal (CommitOutcome.final_outcome). Inject
    # rows write NULL here (filled later by propagate_inject_outcome_
    # from_goal/strategy when produced_goal/strategy terminates) — but
    # Inject returns early via _commit_inject_batch and never reaches
    # this INSERT. Everything that lands here is a synchronous decision:
    # its side effect already executed above, so the row is terminal
    # at INSERT time. RequestUserAmend keeps 'awaiting_human' (terminal
    # from framework POV — blocked on operator). All other kinds
    # (ConfirmShelve/Reopen/EmitDirective/Noop) write 'success'.
    #
    # Pre-fix bug: this column wrote NULL for ConfirmShelve+friends.
    # Solo (batch_id=NULL) was harmless. Paired with Inject in same
    # batch (e.g. ConfirmShelve(G) + a mint Inject for the prereq), the
    # NULL outcome made `maybe_enqueue_inject_batch_done`'s pending
    # count never reach 0 (the batch stayed "incomplete" forever) and
    # the in-flight-inject suppression read the batch as live — so
    # Strategist never woke to fire the promised follow-up Reopen.
    # Observed jordan_normal_form 2026-05-23: ConfirmShelve(succ_glue)
    # paired with Inject of the index-layout brick chain; bricks proved,
    # batch_id stayed "incomplete" forever, the triggers stayed gated,
    # daemon idle. (As of 2026-06-15 the in-flight suppression is a
    # precise active-check — `has_active_inflight_inject` for T4,
    # `has_live_inflight_inject` for T0 / the Noop-guard — not a blanket
    # NULL-row test; but a NULL ConfirmShelve still stalls the batch
    # pending count, so synchronous decisions MUST write a non-NULL
    # outcome here.)
    if outcome == "awaiting_human":
        db_outcome: str | None = "awaiting_human"
    else:
        db_outcome = "success"
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief,"
        " reason, payload, batch_id, outcome, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (problem, tick, trigger_kind, decision.kind, group_id,
         decision.target_id, decision.brief, decision.reason,
         json.dumps(payload_for_audit, ensure_ascii=False),
         inject_batch_id,
         db_outcome,
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
        from ..state import transitions as _transitions
        _transitions.apply_problem_transition(
            conn, problem, "awaiting_human", event="amend_requested")

    # Wake clocks (last_strategist_at + the routine-only last_routine_at)
    # are touched ONCE per batch in `commit_decisions` — not here (task
    # #119: per-path touches let the early-return kinds miss the routine
    # clock).
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
                   intent: "Any",
                   pipeline_id: str,
                   pending_review_id: int | None = None,
                   group_id: "int | None" = None) -> "Any":
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
    # Per-trigger prompt: each trigger has its own focused prompt so
    # the agent sees only the guidance relevant to this wake's kind
    # (routine / pending_review / inject_batch_done).
    # Loader validates that every TRIGGER_KIND has a corresponding
    # file at startup via test_strategist_prompts_cover_all_triggers.
    # A stall wake reads the batch-done prompt: it carries the
    # mandatory-advance rule the rescue exists to invoke (there is no
    # stall.md — the identity split is for the DB record, not for a
    # different conversation).
    _prompt_kind = ("inject_batch_done" if trigger_kind == "stall"
                    else trigger_kind)
    prompt_path = PROMPT_DIR / "strategist" / f"{_prompt_kind}.md"
    if not prompt_path.exists():
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=(
                f"missing prompt file for trigger_kind={trigger_kind!r}: "
                f"{prompt_path}"
            ),
        )

    # Stage 1 — Context.md
    compile_strategist_context(
        conn, problem=problem, trigger_kind=trigger_kind,
        attempts_dir=attempts_dir, workspace=workspace, intent=intent,
        pending_review_id=pending_review_id, group_id=group_id,
    )

    # Stage 2 — agent spawn. Mint a session id so the in-pipeline
    # revision rounds can resume the same claude session and see the
    # framework's verify error / Adversary rebuttal inline.
    # Thinking is legal work (research_mode_design.md §0): the
    # strategist cap is a hang guard, not a work budget.
    strategist_timeout = config.get(
        "strategist.timeout_sec", default=10800,
        env_var="ASTERISM_STRATEGIST_TIMEOUT_SEC", cast=int,
    )
    sid = str(uuid.uuid4())
    # D8 (2026-07-24): a fresh problem has no prior batches — the
    # meta-analysis / reopen-promise paragraphs render only once
    # history exists (conditional blocks, wording untouched).
    has_history = conn.execute(
        "SELECT 1 FROM strategist_decisions WHERE problem = ? LIMIT 1",
        (problem,)).fetchone() is not None
    # has_kb gates the routine wake's lesson-KB curation block — an
    # empty KB renders neither the Context surface nor the instruction.
    from ..state import kb as _kb
    has_kb = bool(_kb.global_lessons(conn, problem))
    # The framework's tools reach this wake over MCP, not a shell (see
    # knowledge/mcp_tools.py). No gateway session: the Strategist has no
    # Lean file open, and registering one would hold a backend slot for
    # nothing.
    from . import write_tools_mcp_config as _write_tools_cfg
    tools_cfg = _write_tools_cfg(attempts_dir, workspace, seat="strategist")
    rc = agent.spawn_llm(
        kind="strategist", prompt_path=prompt_path,
        problem_dir=problem_dir, attempts_dir=attempts_dir,
        session_id=sid, timeout_sec=strategist_timeout,
        mcp_config_path=tools_cfg,
        prompt_flags={"has_history": has_history, "has_kb": has_kb},
    )
    # Persist the plan note BEFORE any outcome branching: the note is the
    # agent's memory of its own thinking — worth keeping even when the
    # spawn then fails parse/verify (and on rc!=0, if it got that far).
    _persist_plan(problem_dir, attempts_dir, group_id)
    if rc != 0:
        return PipelineResult(
            outcome="failed",
            failure_reason=_rc_to_reason(rc),
            failure_detail=f"agent rc={rc}",
        )

    # Stage 3-4 — parse + verify + the proposal-package gate + the
    # Adversary, unified into one N-round revision loop on the same
    # strategist session (research_mode_design.md §3). Mechanical
    # verify errors and Adversary rebuttals SHARE the round counter
    # (v14 ruling). Parse failures get the same single corrective turn
    # as a missing file (2026-08-25 reversal of "malformed means
    # session-level breakage": p324's session was healthy — 10 minutes
    # of research on disk, one malformed decision.json — and died for
    # want of one "rewrite it" turn).
    max_rounds = config.get(
        "strategist.verify_retry", default=6,
        env_var="ASTERISM_STRATEGIST_VERIFY_RETRY", cast=int,
    )
    decision_path = attempts_dir / "decision.json"

    # Quota-park budget for this wake (2026-08-08). A debate that
    # collides with the subscription reset must sleep to it rather than
    # burn the accumulated rounds — but only so far: the queue row's
    # lease is reclaimed on AGE alone at LEASE_TTL_SEC even with this
    # thread alive, and a reclaimed row means a second Strategist on
    # this same group. Budget = what is left of 80% of the TTL after
    # everything this wake has already spent.
    _wake_t0 = _time.monotonic()

    def _park_budget() -> float:
        from ..core.dispatcher import LEASE_TTL_SEC
        return (LEASE_TTL_SEC * 0.8) - (_time.monotonic() - _wake_t0)

    def _quota_park(label: str) -> bool:
        from ..core import quota_wait as _qw
        return _qw.park_in_pipeline(f"{problem} {label}",
                                    budget_sec=_park_budget())

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
    if missing or decisions is None:
        # One corrective turn before the wake dies at the file stage.
        # Three shapes end a session with the WORK all there but no
        # usable decision.json: the model narrates its decision in
        # prose instead of calling write_file, OpenCode occasionally
        # ends a healthy stream early with a near-empty final that the
        # tool loop accepts as the answer (5/46 wakes on the flagship's
        # first generations, 2026-08-25 — each death threw away 20+
        # minutes of research), and the file lands malformed past what
        # the lenient parse absorbs (p324, same day). Resuming the SAME
        # session costs one cheap turn and keeps everything it learned;
        # a second miss still dies below.
        _defect = missing or f"decision.json does not parse ({parse_err})"
        print(f"[strategist] {problem}: {_defect} — one corrective "
              f"resume turn", flush=True)
        rc_fix = agent.spawn_llm(
            kind="strategist", prompt_path=prompt_path,
            problem_dir=problem_dir, attempts_dir=attempts_dir,
            session_id=sid, is_retry=True,
            retry_context=(
                ("Your turn ended but decision.json was NOT written — "
                 "the research is only real once it lands on disk. "
                 "Write decision.json NOW with write_file (and "
                 "proposal.md if your batch carries one). If your last "
                 "message was cut off, reconstruct the decision from "
                 "your notes above.")
                if missing else
                (f"Your decision.json is not valid JSON — {parse_err}. "
                 "Rewrite the ENTIRE file NOW with write_file as one "
                 "valid JSON array of decision objects; keep the same "
                 "decisions, fix only the syntax.")),
            timeout_sec=strategist_timeout,
            mcp_config_path=tools_cfg,
        )
        _persist_plan(problem_dir, attempts_dir, group_id)
        if rc_fix == 0:
            decisions, parse_err, missing = _read_and_parse()
    if missing:
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail=missing + " (after one corrective turn)",
        )
    if decisions is None:
        return PipelineResult(
            outcome="failed",
            failure_reason="strategist_schema_invalid",
            failure_detail=f"parse: {parse_err} (after one corrective turn)",
        )

    from ..state import programme as _programme
    from . import adversary as _adversary

    dialogue: list[dict] = []
    rounds_used = 0
    package_verdict: "dict | None" = None
    proposal_body: "str | None" = None
    first_err: "str | None" = None
    while True:
        # Round-boundary race-guard: the authoring group can be retired
        # mid-dialogue (ancestor ReturnToParent cascade). Ask before
        # spending a verify + adversary round — the batch of a retired
        # charter has nowhere legal to land, so the wake self-aborts
        # instead of debating on (fold day 2026-08-19: 11 rounds burned
        # past the flip). The commit door below backstops the window
        # between this check and Stage 5.
        _retired = _group_retired_status(conn, problem, group_id)
        if _retired is not None:
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                f"authoring group retired ({_retired}) mid-wake",
                attempts_dir, group_id=group_id, channel="group_retired")
            return PipelineResult(
                outcome="failed", failure_reason="group_retired",
                failure_detail=(
                    f"group {group_id} is {_retired}; a retired charter "
                    "accepts no new batch"))
        err = verify_decisions(decisions, conn, problem=problem,
                               workspace=workspace,
                               trigger_kind=trigger_kind,
                               group_id=group_id)
        err_is_rebuttal = False
        if not err and package_gate_applies(decisions, trigger_kind):
            proposal_body, sections, err = verify_proposal_package(
                decisions, attempts_dir)
            if not err:
                proof_warn = _programme.length_warning(
                    sections, proposal_body)
                if proof_warn:
                    print(f"[strategist] {problem}: {proof_warn}",
                          flush=True)
                verdict, aerr, arc = _adversary.review(
                    round_no=rounds_used + 1,
                    attempts_dir=attempts_dir, problem_dir=problem_dir,
                    conn=conn, problem=problem,
                    proposal_body=proposal_body, decisions=decisions,
                    dialogue=dialogue, proof_warn=proof_warn,
                    group_id=group_id, quota_park=_quota_park)
                if arc != 0:
                    _discard_proposal(
                        conn, problem, proposal_body, dialogue,
                        rounds_used,
                        f"adversary spawn rc={arc}", attempts_dir,
                        group_id=group_id,
                        channel=_adversary_rc_reason(arc))
                    return PipelineResult(
                        outcome="failed",
                        failure_reason=_adversary_rc_reason(arc),
                        failure_detail=f"adversary rc={arc}")
                if verdict is None:
                    _discard_proposal(
                        conn, problem, proposal_body, dialogue,
                        rounds_used,
                        "adversary produced no ruling", attempts_dir,
                        group_id=group_id, channel="agent_no_output")
                    return PipelineResult(
                        outcome="failed",
                        failure_reason="agent_no_output",
                        failure_detail=f"adversary: {aerr}")
                if verdict["verdict"] == "pass":
                    package_verdict = verdict
                    break
                # Rebuttal: the criticisms target THIS body — keep it
                # with them so the next (fresh) judge reads the round
                # as documents (fresh-per-round, design §3).
                dialogue.append({"round": rounds_used + 1,
                                 "role": "adversary",
                                 "criticisms": verdict["criticisms"],
                                 "proposal": proposal_body})
                # rounds_left = revisions still available AFTER this
                # rebuttal: a retry fires whenever rounds_used <
                # max_rounds, so exactly max_rounds - rounds_used
                # remain (off-by-one here once taught "0 left" while
                # the loop granted one more).
                err = _format_rebuttal(
                    verdict, rounds_used + 1,
                    max_rounds - rounds_used,
                    length_warn=proof_warn)
                err_is_rebuttal = True
        if not err:
            break  # verify clean; exempt batches skip the package gate
        if first_err is None:
            first_err = err
        if rounds_used >= max_rounds:
            if err_is_rebuttal and proposal_body is not None:
                # Exhaustion on the adversarial channel discards the
                # proposal AND the session: the rejected draft + full
                # criticism go to the DB for audit; the next wake gets
                # one line and re-derives blind (design §1/§3).
                _discard_proposal(
                    conn, problem, proposal_body, dialogue, rounds_used,
                    "adversary rebuttal", attempts_dir,
                    group_id=group_id,
                    channel="strategist_proposal_rejected")
                return PipelineResult(
                    outcome="failed",
                    failure_reason="strategist_proposal_rejected",
                    failure_detail=(
                        f"adversary rejected after {rounds_used} "
                        "revision round(s); proposal + criticisms "
                        "recorded in programme_revisions"))
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                "package verify rejected", attempts_dir,
                group_id=group_id,
                channel="strategist_schema_invalid")
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(f"verify (round {rounds_used}): {err}; "
                                f"first-attempt: {first_err}"),
            )
        rounds_used += 1
        # Same class as the judge's infra retry (task #132): this wake
        # already holds a parsed batch (and possibly rounds of
        # criticism); a provider-side rc on the revision spawn must cost
        # a re-spawn, not the accumulated work. Session id is reused —
        # `--resume` on the same sid is what carries the revision.
        _infra_tries = 0
        while True:
            rc2 = agent.spawn_llm(
                kind="strategist", prompt_path=prompt_path,
                problem_dir=problem_dir, attempts_dir=attempts_dir,
                session_id=sid, is_retry=True, retry_context=err,
                timeout_sec=strategist_timeout,
                mcp_config_path=tools_cfg,
            )
            if rc2 != 0 and _failures.is_infra(_rc_to_reason(rc2)):
                # Ask the ledger BEFORE spending the retry budget: an
                # expired subscription window announces its own end
                # time, and 2×15s against it is what cost an 8-round
                # debate (2026-08-07). Parking resumes the SAME sid, so
                # the author keeps its position in the argument.
                if _quota_park(f"revision round {rounds_used}"):
                    continue
            if (rc2 != 0
                    and _failures.is_infra(_rc_to_reason(rc2))
                    and _infra_tries < _adversary.INFRA_SPAWN_RETRIES):
                _infra_tries += 1
                print(f"[strategist] {problem}: revision round "
                      f"{rounds_used} spawn rc={rc2} (infra) — retry "
                      f"{_infra_tries}/{_adversary.INFRA_SPAWN_RETRIES} "
                      f"in {_adversary.INFRA_RETRY_BACKOFF_SEC:.0f}s",
                      flush=True)
                _time.sleep(_adversary.INFRA_RETRY_BACKOFF_SEC)
                continue
            break
        _persist_plan(problem_dir, attempts_dir, group_id)  # retry may rewrite it
        if rc2 != 0:
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                f"revision spawn rc={rc2}", attempts_dir,
                group_id=group_id, channel=_rc_to_reason(rc2))
            return PipelineResult(
                outcome="failed",
                failure_reason=_rc_to_reason(rc2),
                failure_detail=(
                    f"revision round {rounds_used} rc={rc2}; "
                    f"pending: {err}"
                ),
            )
        decisions, parse_err, missing = _read_and_parse()
        if missing or decisions is None:
            detail = missing or f"parse: {parse_err}"
            _discard_proposal(
                conn, problem, proposal_body, dialogue, rounds_used,
                "revision round produced no decision.json",
                attempts_dir, group_id=group_id,
                channel="strategist_schema_invalid")
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=(
                    f"revision round {rounds_used} output: {detail}; "
                    f"pending: {err}"
                ),
            )

    # Stage 5 — commit + outcome mapping
    # Commit door: last look before side effects. The round loop above
    # checks at every boundary, but the group can flip terminal between
    # the final pass verdict and here; `commit_decisions` itself raises
    # on this as the any-caller backstop, and a raise there would be
    # mis-filed as a framework bug — so the known race exits cleanly.
    _retired = _group_retired_status(conn, problem, group_id)
    if _retired is not None:
        _discard_proposal(
            conn, problem, proposal_body, dialogue, rounds_used,
            f"authoring group retired ({_retired}) before commit",
            attempts_dir, group_id=group_id, channel="group_retired")
        return PipelineResult(
            outcome="failed", failure_reason="group_retired",
            failure_detail=(
                f"group {group_id} is {_retired}; a retired charter "
                "accepts no new batch"))
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
                group_id=group_id,
            )
        except Exception as e:
            return PipelineResult(
                outcome="failed",
                failure_reason="strategist_schema_invalid",
                failure_detail=f"commit raised: {type(e).__name__}: {e}",
            )
        if trigger_kind == "routine":
            _apply_kb_curation(conn, problem=problem,
                               attempts_dir=attempts_dir)
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
            group_id=group_id,
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

    if package_verdict is not None and proposal_body is not None:
        # Passed proposal → the Programme revision chain advances in
        # the same wake as its batch (rev↔batch link via batch_id).
        # PROGRAMME.md render is best-effort — the DB row is the SoT.
        batch_id = next(
            (o.batch_id for o in outcomes if o.batch_id), None)
        _programme.record_pass(
            conn, problem, proposal_body, package_verdict, dialogue,
            rounds_used, batch_id, group_id=group_id)
        conn.commit()
        try:
            _programme.render(conn, problem, problem_dir,
                              group_id=group_id)
        except OSError as e:
            print(f"[strategist] PROGRAMME.md render failed: {e}",
                  flush=True)

    if trigger_kind == "routine":
        # Curation applies only after the wake's decisions committed —
        # a rejected batch (retry loop above) must not half-apply a
        # sidecar the agent may still rewrite.
        _apply_kb_curation(conn, problem=problem,
                           attempts_dir=attempts_dir)

    kinds = ",".join(d.kind for d in decisions)
    row_ids = ",".join(str(o.decision_row_id) for o in outcomes)
    # Framework feedback (dedicated tail step) — fired here, after every
    # `--resume <sid>` (main + optional verify-retry) is done, so the feedback
    # turn never pollutes a verify-retry's session. No-op unless feedback is on.
    from . import _feedback
    _feedback.attempt_feedback(
        kind="strategist", seat="strategist", sid=sid,
        slug=str(trigger_kind or "strategist"),
        outcome="success", problem_dir=problem_dir,
        attempts_dir=attempts_dir, workspace=workspace)
    return PipelineResult(
        outcome="success",
        failure_reason="",
        failure_detail=(
            f"committed {len(decisions)} decision(s): [{kinds}] "
            f"(decision_rows=[{row_ids}])"
        ),
    )


_KB_CURATION_MAX_OPS = 10


def _apply_kb_curation(conn: "Any", *, problem: str,
                       attempts_dir: Path) -> None:
    """Routine-wake KB curation (2026-07-13, user call; moved from the
    retired audit wake 2026-07-25): apply the optional
    `kb_curation.json` sidecar the agent may drop next to
    decision.json. Ops:

      {"op": "delete", "id": N, "reason": "..."}
      {"op": "merge", "keep_id": N, "absorb_ids": [..],
       "title": "...", "body": "...", "reason": "..."}

    Deliberately a sidecar, NOT a decision kind: curation is
    belief-store maintenance (same class as the direct `_plan.md`
    curation), never problem-state advance — keeping it out of
    decision.json means it can never satisfy the stall-advance delta
    gate, and no DB CHECK migration is needed. Only the routine runner
    calls this, so the power is structurally routine-only.

    Strict all-or-nothing: any invalid op rejects the whole file with
    a loud `[kb-curation]` line and nothing is applied — but the wake
    itself never fails on it (the sidecar is best-effort; the wake's
    deliverables are its decisions + note). Applied ops print full
    pre-image snapshots to the daemon log as the audit trail."""
    from ..state import kb

    path = attempts_dir / "kb_curation.json"
    if not path.exists():
        return

    def _reject(msg: str) -> None:
        print(f"[kb-curation] {problem}: rejected, nothing applied — "
              f"{msg}", flush=True)

    try:
        ops = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _reject(f"unreadable/invalid JSON: {e}")
    if not isinstance(ops, list) or not ops:
        return _reject("must be a non-empty JSON array of ops")
    if len(ops) > _KB_CURATION_MAX_OPS:
        return _reject(f"{len(ops)} ops exceeds the per-wake cap of "
                       f"{_KB_CURATION_MAX_OPS}")

    eligible = {int(r["id"]) for r in kb.global_lessons(conn, problem)}
    seen_ids: set[int] = set()

    def _claim(raw: "Any", i: int, field: str) -> int | None:
        if not isinstance(raw, int) or isinstance(raw, bool):
            _reject(f"op #{i}: {field} must be an integer id")
            return None
        if raw not in eligible:
            _reject(f"op #{i}: id {raw} is not one of this problem's "
                    "global lessons")
            return None
        if raw in seen_ids:
            _reject(f"op #{i}: id {raw} referenced by more than one op")
            return None
        seen_ids.add(raw)
        return raw

    parsed: list[dict] = []
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            return _reject(f"op #{i}: not a JSON object")
        if not str(op.get("reason", "")).strip():
            return _reject(f"op #{i}: non-empty source-checked 'reason' "
                           "is required")
        kind = op.get("op")
        if kind == "delete":
            if _claim(op.get("id"), i, "id") is None:
                return None
        elif kind == "merge":
            if _claim(op.get("keep_id"), i, "keep_id") is None:
                return None
            absorb = op.get("absorb_ids")
            if not isinstance(absorb, list) or not absorb:
                return _reject(f"op #{i}: absorb_ids must be a non-empty "
                               "list")
            for a in absorb:
                if _claim(a, i, "absorb_ids entry") is None:
                    return None
            if not str(op.get("title", "")).strip():
                return _reject(f"op #{i}: merged 'title' must be "
                               "non-empty")
        else:
            return _reject(f"op #{i}: unknown op {kind!r} (delete|merge)")
        parsed.append(op)

    for op in parsed:
        if op["op"] == "delete":
            snap = kb.delete_global_lesson(
                conn, entry_id=op["id"], problem=problem)
            print(f"[kb-curation] {problem}: deleted lesson "
                  f"[id-{op['id']}] reason={op['reason']!r} "
                  f"snapshot={dict(snap) if snap else None}", flush=True)
        else:
            snaps = kb.merge_global_lessons(
                conn, keep_id=op["keep_id"],
                absorb_ids=[int(a) for a in op["absorb_ids"]],
                problem=problem, title=str(op["title"]),
                body=str(op.get("body", "")))
            print(f"[kb-curation] {problem}: merged "
                  f"{op['absorb_ids']} into [id-{op['keep_id']}] "
                  f"reason={op['reason']!r} "
                  f"pre-images={[dict(r) for r in snaps or []]}",
                  flush=True)


def _discard_proposal(conn, problem: str,
                      proposal_body: "str | None",
                      dialogue: list, rounds_used: int,
                      reason: str,
                      attempts_dir: "Path | None" = None,
                      group_id: "int | None" = None,
                      channel: "str | None" = None) -> None:
    """Record a proposal that did NOT commit, whichever channel dropped
    it (Adversary refutation / package verify / revision spawn failure /
    unusable revision output).

    Pre-v34 only the Adversary path left a row, so a batch dropped by
    the mechanical channels vanished without trace while its plan note
    — persisted before the batch is judged — survived asserting the
    dispatch. The next wake then had to reconstruct that from three
    artifacts (07-29 SG ×2). No proposal at all (exempt batch: Noop /
    RequestUserAmend / FetchPaper) → nothing to record; the plan note's
    provenance stamp still covers those.

    `attempts_dir` is the fallback source: an early verify rejection
    fires BEFORE the package gate reads `proposal.md`, so the body the
    agent wrote exists only on disk at that point."""
    if not proposal_body and attempts_dir is not None:
        try:
            proposal_body = (attempts_dir / PROPOSAL_BASENAME).read_text(
                encoding="utf-8")
        except OSError:
            proposal_body = None
    if not proposal_body:
        return
    from ..state import programme as _programme
    try:
        _programme.record_rejection(conn, problem, proposal_body,
                                    dialogue, rounds_used,
                                    discard_reason=reason,
                                    group_id=group_id,
                                    discard_channel=channel)
        conn.commit()
    except Exception as e:  # noqa: BLE001 — audit record, never fatal
        print(f"[strategist] {problem}: discard record failed: "
              f"{type(e).__name__}: {e}", flush=True)


def _persist_plan(problem_dir: Path, attempts_dir: Path,
                  group_id: "int | None" = None) -> None:
    """Persist the Strategist's `_plan.md` (private cross-wake note, see
    `_drafts.persist_plan_note`) + one telemetry line. Best-effort."""
    from . import _drafts
    n = _drafts.persist_plan_note(problem_dir=problem_dir,
                                  attempts_dir=attempts_dir,
                                  group_id=group_id)
    if n is not None:
        over = (" (over soft cap)"
                if n > _drafts.PLAN_NOTE_SOFT_CAP else "")
        print(f"[strategist] plan note updated: {n} chars{over}",
              flush=True)


def _rc_to_reason(rc: int, kind: str = "strategist") -> str:
    """Channel failure_reason for an agent rc — thin alias of the registry's
    `failures.rc_to_reason` (task #5: the last per-pipeline mirror of the rc
    taxonomy; kept as a module-local name for the two call sites + tests).

    `kind` names the seat, which is how the provider's `rc_contract`
    declaration is found. The Strategist and the Adversary sit on
    different providers routinely (2026-08 runs: NL on opus-5, judge
    moved between seats mid-run), so an rc from the judge must be read
    against the JUDGE's contract, not the author's."""
    from ..llm import capabilities as _caps
    from ..state.failures import rc_to_reason
    return rc_to_reason(rc, rc_contract=_caps.for_kind(kind).rc_contract)


def _adversary_rc_reason(rc: int) -> str:
    """The judge's rc, read against the JUDGE's seat. A named function
    rather than an inline second argument: a bare string literal beside
    `failure_reason=` is what the registry's AST drift scan reads as a
    new failure reason."""
    return _rc_to_reason(rc, "adversary")
    if rc == 126:
        return "quota_exhausted"
    if rc == 127:
        return "missing_dep"
    if rc == 128:
        return "spawn_fast_fail"  # stuck thinking — treat as infra
    return "spawn_fast_fail"
