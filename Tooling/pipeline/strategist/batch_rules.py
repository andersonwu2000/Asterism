"""Cross-decision batch rules — every refusal a BATCH earns, at once.

Split out of `verify.py` 2026-09-08 (the split that file's watermark has
been owed since 08-28). The per-decision gates stay there; what moved is
the layer that only exists because several decisions land in one call.

WHY THEY ARE COLLECTED, NOT RETURNED ONE AT A TIME
--------------------------------------------------
These rules used to run in sequence with an early `return`, so a batch
saw exactly one of them per wake. That is affordable while the remedies
compose — and it is a trap the moment they do not, because the message
the agent receives PRESCRIBES a shape, and the next gate can refuse the
very shape the last one prescribed.

Observed p617, 2026-09-08 13:12Z and again 13:17Z with the identical
batch: the cascade rule (`ConfirmShelve(anc)` + `Inject(descendant)`)
said "drop the ConfirmShelve and `Inject(target=11075)`". The Strategist
did exactly that; the review-discharge rule then refused the result,
because the goals waiting on a verdict were `{11093, 11098}` and 11075
is not one of them. Its remedy — target a waiting goal — walks back into
the cascade rule, and `ConfirmShelve` alone walks into the pairing rule.
Three gates, three correct rules, and no path between them that one wake
can find, because each wake is shown one third of the constraint.

So the batch verifier collects EVERY cross-decision refusal, and then
answers the question the agent actually has: what does a batch look like
that satisfies all of them at once. The answer is computed, not
described — `repair_batch` applies each refusal's structured remedy to
the submitted decisions, and the composed shape is RE-CHECKED through
the same rules before it is offered. If the re-check is clean the
message names it; if it is not, the message says the constraints
conflict and names the rule that is still refusing, which is the honest
answer and the one that tells the owner a design decision is due.

Each rule therefore carries two things: the prose it always carried
(unchanged — those messages are load-bearing and field-tested), and a
machine-readable remedy (`CrossRefusal`'s `drop` / `inject_targets` /
`target_one_of` / `needs_inject`) that the composer can act on.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from ...state import db
from .model import BATCH_DONE_LIKE, Decision


@dataclass
class CrossRefusal:
    """One cross-decision rule's refusal, with its remedy in a form the
    composer can apply.

    `message` is what the agent reads. The rest is how a batch that
    satisfies this rule can be BUILT:

      * `drop` — `(kind, target_id)` decisions that must leave the batch;
      * `inject_targets` — goals that each need an `Inject` aimed at them;
      * `target_one_of` — goals of which AT LEAST ONE must be the target
        of some decision in the batch;
      * `needs_inject` — the batch must dispatch at least one `Inject`,
        whatever its target.
    """
    message: str
    drop: "tuple[tuple[str, int | None], ...]" = ()
    inject_targets: "tuple[int, ...]" = ()
    target_one_of: "tuple[int, ...]" = ()
    needs_inject: bool = False


def _target_int(d) -> "int | None":
    t = getattr(d, "target_id", None)
    if t is None:
        return None
    try:
        return int(t)
    except (TypeError, ValueError):
        return None


def cross_decision_refusals(
        decisions: "list[Decision]", conn: sqlite3.Connection, *,
        problem: str, trigger_kind: str = "",
        group_id: "int | None" = None) -> "list[CrossRefusal]":
    """EVERY cross-decision rule that refuses this batch, in rule order.

    The premise is unchanged from when these ran inside
    `verify.verify_decisions`: each decision is already individually
    valid, so what is left to check is the combination.
    """
    refusals: "list[CrossRefusal]" = []
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
        lone = next(d for d in decisions if d.kind == "Delegate")
        refusals.append(CrossRefusal(
            "A batch delegates several groups or none — never exactly "
            "one: a lone Delegate is your own next step wearing a new "
            "group. Split the burden into parallel lines and delegate "
            "them together (two groups may even race the same goal), "
            "or keep single-line work in your Roadmap's AHEAD — the "
            "next wake fires when this batch completes.",
            # The composer can only take the second branch mechanically
            # (a second Delegate needs a burden only the author has);
            # the first stays named in the prose above.
            drop=(("Delegate", _target_int(lone)),)))

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
        refusals.append(CrossRefusal(
            f"batch contains both ConfirmShelve and a goal-targeted "
            f"Inject for goal {gid} — the Inject force-reopens the "
            f"target, the ConfirmShelve then shelves it; the queued "
            f"retry would dispatch on a shelved goal. Drop the "
            f"ConfirmShelve (the redispatch already keeps the goal "
            f"alive) or aim the Inject at a different goal.",
            drop=(("ConfirmShelve", gid),)))

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
        for ij_target in sorted(inject_bb_targets):
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
                refusals.append(CrossRefusal(
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
                    f"{anc_id}, brick=\"…the brick whose Proof retries"
                    f" the whole subtree…\") to re-attack it with the"
                    f" sub-rescue argument; OR keep the ConfirmShelve and"
                    f" drop this Inject (the descendant is acknowledged"
                    f" as cascade-dead).",
                    drop=(("ConfirmShelve", anc_id),),
                    inject_targets=(anc_id,)))
                break

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
    # "still parked" verdict — forcing an Inject onto it mints a fresh
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
            refusals.append(CrossRefusal(
                "ConfirmShelve must be paired with at least one Inject "
                "decision in the same batch. EmitDirective alone (notes) "
                "and RequestUserAmend alone (user escalation) do not "
                "count — they don't dispatch a fresh attempt or redirect "
                "focus. Pair with one of:\n"
                "  - Inject(brick=..., no target) to mint the missing "
                "tool the shelved goal needed.\n"
                "  - Inject(target_goal_id=..., "
                "brick=...) to redispatch another goal (typically the "
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
                "gate).",
                needs_inject=True))

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
    # Scope: the wake's CONTEXT, not its trigger (owner ruling
    # 2026-09-05). Every wake that reaches this gate is handed the
    # dossier of every waiting goal (`phase2_context.compile`, same
    # query), so every wake that reaches it owes the verdict. The
    # 2026-07-12 exemption for `routine` was written when a routine wake
    # still committed decisions and could be bounced by this rule; the
    # routine wake is an AUDIT now (verdict.json, no verify pass), so
    # the exemption guards nothing here and only left a trigger name
    # that could read a review and answer around it — the one bypass
    # T2's batch suppression must not re-open.
    pending_review_ids: set[int] = {
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
            refusals.append(CrossRefusal(
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
                f"the whole batch.",
                target_one_of=tuple(sorted(pending_review_ids))))

    # Cross-decision: stall-advance (problem FSM design §3.1,
    # 2026-07-12 — the pure-NL re-confirm pump). Forced advance is THE
    # design philosophy; its old mechanical anchor was the root status,
    # so a rootless (pure-NL) problem had no enforcement and the gate
    # counted decision KINDS, not state deltas — a zero-delta batch
    # (re-confirm shelve / Noop / re-mark) passed as action. New
    # currency: `predicted_batch_delta` (transitions §2.3) — a stalled
    # wake with nothing live in flight must move ≥1 state or dispatch
    # ≥1 new piece of work, root or no root.
    if trigger_kind == "routine_fired" and group_id is not None:
        # The action wake exists to act on the audit's findings: every
        # fired root must be the target of a decision in this batch —
        # parked (ConfirmShelve, restart condition in PAST) or kept with
        # its argument (Inject). A structural check on decision targets,
        # never on prose (owner design 2026-08-30).
        from . import audit as _audit
        pending = _audit.pending_fired_verdict(conn, int(group_id))
        if pending is not None:
            fired = json.loads(str(pending["fired_json"] or "[]"))
            targets: set[int] = set()
            for d in decisions:
                # The model's field is `target_id` (decision.json says
                # `target_goal_id`; the parser folds both). Reading the
                # JSON key name here made this gate reject EVERY correct
                # batch in the field (experiment 1, 2026-08-30).
                t = getattr(d, "target_id", None)
                if t is None:
                    continue
                try:
                    targets.add(int(t))
                    continue
                except (TypeError, ValueError):
                    pass
                row = conn.execute(
                    "SELECT id FROM goals WHERE problem = ? AND slug = ?",
                    (problem, str(t))).fetchone()
                if row is not None:
                    targets.add(int(row["id"]))
            untouched = []
            for f in fired:
                gid_f = f.get("goal_id")
                if gid_f is None or int(gid_f) in targets:
                    continue
                # A fired root that has since left the live set (shelved /
                # proved / disproved by another path) is not a line this batch
                # can act on — only live roots are required.
                cur = conn.execute("SELECT status FROM goals WHERE id = ?",
                                   (int(gid_f),)).fetchone()
                if cur is None or str(cur["status"]) not in _audit.LIVE_ROOT_STATUSES:
                    continue
                untouched.append(f)
            if untouched:
                lines = "\n".join(
                    f"  - `{f.get('slug')}` (goal_id {f.get('goal_id')}): "
                    f"criterion {f.get('criterion')} — {f.get('reason')}"
                    for f in untouched)
                refusals.append(CrossRefusal(
                    f"routine audit {int(pending['id'])} fired on lines "
                    f"this batch leaves untouched:\n{lines}\n"
                    f"Act on every fired root: `ConfirmShelve` it (its "
                    f"restart condition in the Roadmap's PAST) or "
                    f"`Inject(target_goal_id=...)` it with the argument "
                    f"that keeps it. Other decisions may accompany these.",
                    inject_targets=tuple(
                        int(f["goal_id"]) for f in untouched
                        if f.get("goal_id") is not None)))

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
            from ...state import transitions as _transitions
            if _transitions.predicted_batch_delta(conn, decisions) < 1:
                refusals.append(CrossRefusal(
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
                    "propose the hypothesis, then argue rigorously "
                    "whether it holds — face the unknown with the courage "
                    "of long thought, look for clues and reach for a "
                    "genuinely new idea.\n"
                    "Commit the work as: `Inject` (a genuinely new angle) "
                    "/ `ConfirmShelve` (a live goal) paired with an "
                    "`Inject` / `MarkDeliverable` (a "
                    "PROVED forward node) then `Ingest`. "
                    "`RequestUserAmend` ONLY if a user file is factually "
                    "WRONG — difficulty or a missing API is work, not "
                    "wrongness. `Noop` may accompany, never alone.",
                    needs_inject=True))

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
    # `disproved` roots intentionally NOT covered: a kernel-certified
    # counterexample is a genuine dead end where the Strategist cannot
    # recover; Noop is the right acknowledgement.
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
                refusals.append(CrossRefusal(
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
                    f"  - `Inject(brick=...)` / `Delegate(...)` to "
                    f"dispatch the work still missing (root stays "
                    f"{rstat!r}; inject_batch_done will re-fire you), "
                    f"OR\n"
                    f"  - the root subtree is yours and the toolkit is "
                    f"ready → `Inject(target_goal_id={rid}, brick=...)` "
                    f"re-engages BFS on it, OR\n"
                    f"  - `RequestUserAmend(...)` ONLY if a user file is "
                    f"factually wrong.",
                    needs_inject=True))
    return refusals


# ---------------------------------------------------------------------
# composing ONE answer out of several refusals
# ---------------------------------------------------------------------

def repair_batch(decisions: "list[Decision]",
                 refusals: "list[CrossRefusal]") -> "list[Decision]":
    """The submitted batch with every refusal's structured remedy applied.

    Drops come first (a decision a rule refuses cannot be kept by
    another rule's remedy), then the injects the remaining rules need.
    A goal already targeted by a surviving decision is never given a
    second one — the rules ask for a decision ON the goal, and two
    aimed at the same goal is a batch shape of its own.
    """
    drops = {d for r in refusals for d in r.drop}
    kept = [d for d in decisions
            if (d.kind, _target_int(d)) not in drops]
    added: "list[Decision]" = []
    targeted = {t for t in (_target_int(d) for d in kept) if t is not None}

    def _add(target: "int | None") -> None:
        added.append(Decision(kind="Inject", target_id=target,
                              payload={"brick": "<name the brick>"}))
        if target is not None:
            targeted.add(target)

    for r in refusals:
        for t in r.inject_targets:
            if t not in targeted:
                _add(t)
    for r in refusals:
        if r.target_one_of and not (set(r.target_one_of) & targeted):
            _add(min(r.target_one_of))
    if (any(r.needs_inject for r in refusals)
            and not any(d.kind == "Inject" for d in kept + added)):
        _add(None)
    return kept + added


def _shape_line(d: "Decision") -> str:
    t = _target_int(d)
    if d.kind == "Inject":
        return (f"Inject(target_goal_id={t}, brick=…)" if t is not None
                else "Inject(brick=…)  ← a mint, no target")
    return f"{d.kind}({t})" if t is not None else d.kind


def compose(decisions: "list[Decision]", refusals: "list[CrossRefusal]",
            conn: sqlite3.Connection, *, problem: str,
            trigger_kind: str = "",
            group_id: "int | None" = None) -> str:
    """One message for several cross-decision refusals.

    A single refusal is returned as it always was — its own prose names
    a remedy no other rule contradicts. From two up, the prose alone is
    a trap (see this module's docstring), so the message carries all of
    them AND one concrete batch shape, which is built by `repair_batch`
    and then RE-CHECKED through the same rules. Offering an unchecked
    shape would be the same defect one level up.
    """
    if not refusals:
        return ""
    if len(refusals) == 1:
        return refusals[0].message
    head = (f"{len(refusals)} batch-level rules refuse this batch AT ONCE. "
            f"Fixing them one at a time cannot work — each one's remedy "
            f"is refused by another, so here they are together, with one "
            f"shape that satisfies all {len(refusals)}:\n")
    body = "\n".join(f"({i + 1}) {r.message}"
                     for i, r in enumerate(refusals))
    fixed = repair_batch(decisions, refusals)
    left = cross_decision_refusals(fixed, conn, problem=problem,
                                   trigger_kind=trigger_kind,
                                   group_id=group_id)
    if left:
        # No shape built from these decisions satisfies every rule. Say
        # so, and name what is still refusing: the resolution is a
        # judgement only the author can make (drop a line of work,
        # deliver, or escalate), and a verifier that invented one would
        # be prescribing research.
        still = "; ".join(r.message.split("\n")[0] for r in left)
        return (head + body + "\n\nTHESE CONSTRAINTS CONFLICT: applying "
                "every remedy above still leaves — " + still + "\n"
                "No batch of these decisions satisfies all of them. "
                "Decide which line of work you are dropping (its "
                "`ConfirmShelve` reason is where that goes), or exit the "
                "group (`MarkDeliverable` + `Ingest`), or escalate with "
                "`RequestUserAmend` if a user file is what is wrong.")
    drops = [d for d in decisions if d not in fixed]
    shape = ["\nOne batch that satisfies all of them:"]
    for d in drops:
        shape.append(f"  - DROP {_shape_line(d)}")
    for d in fixed:
        if d in decisions:
            shape.append(f"  - keep {_shape_line(d)}")
        else:
            shape.append(f"  - ADD  {_shape_line(d)}")
    for r in refusals:
        if len(r.target_one_of) > 1:
            ids = ", ".join(f"g{i}" for i in sorted(r.target_one_of))
            shape.append(f"    (any one of {ids} discharges the review — "
                         f"the one above is this message's pick, not the "
                         f"only legal answer)")
    shape.append("Every added Inject still needs its own brick name and "
                 "the argument that makes it worth dispatching — the "
                 "shape is the part the verifier can compute, not the "
                 "research.")
    return head + body + "\n" + "\n".join(shape)
