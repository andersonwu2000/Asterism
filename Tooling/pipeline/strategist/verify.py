"""Schema validation (self_verify stage): `verify_decision` +
`verify_decisions`, the authoring-group helpers they share
(`_authoring_group`, `_group_retired_status`), and `USER_AMEND_FILES`
(the RequestUserAmend file allow-list — its only consumer is this
module's `verify_decision`, so it moved here rather than with the
decision-kind vocabulary in `model.py`).

Split out of `strategist.py` 2026-08-28 (Phase B, B1) unchanged.
`_authoring_group` / `_group_retired_status` are the two names `commit.py`
and `wake.py` import back from here — both consume the group's retired-
status race-guard.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ...core import dispatcher as _dispatcher
from ...state import db, transitions
from ...state import programme as _programme
from ...state import groups as _groups

from . import batch_rules as _batch_rules
from .model import Decision, RETURN_FLAVOURS, brick_name_of


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


#: HID §1.2: the terminal must hand a mathematician a readable summary
#: (`Ingest.report` → `problems.ingest_report` → `REPORT.md`), so an
#: Ingest without one does not close a problem. Unconditional since
#: 2026-09-02, when the wording that asks for the field went live in the
#: three wake prompts — a gate that refuses a field the Strategist was
#: never asked for teaches nothing, which is what the retired
#: `INGEST_REPORT_REQUIRED` flag was holding back.
#:
#: The report's shape (owner ruling 2026-09-02): a short PAPER, and a
#: paper has these four parts in this order. Structure is the whole of
#: what a gate can check — a length floor buys padding and a banned-word
#: list buys synonyms, and neither can tell whether the prose is any
#: good. The four headings are what a reader navigates by, and they are
#: mechanical: present, exact, at line start, in order.
INGEST_REPORT_SECTIONS = ("## Introduction", "## Main Result",
                          "## Proof Sketch", "## What Remains")


def _ingest_report_defect(report: str) -> str:
    """'' when `report` carries the four headings in order, else the
    refusal — naming the heading at fault AND quoting the whole order,
    because a gate that only says "wrong" costs a wake to guess."""
    order = ", then ".join(f"`{h}`" for h in INGEST_REPORT_SECTIONS)
    at: dict[str, int] = {}
    for i, ln in enumerate(report.splitlines()):
        h = ln.rstrip()
        if h in INGEST_REPORT_SECTIONS and h not in at:
            at[h] = i
    missing = [h for h in INGEST_REPORT_SECTIONS if h not in at]
    if missing:
        return (f"Ingest.report is missing "
                f"{', '.join(f'`{h}`' for h in missing)} — the report is a "
                f"short paper for a mathematician who has never seen this "
                f"system, with these four headings, each alone on its "
                f"line, in this order: {order}")
    seen = [at[h] for h in INGEST_REPORT_SECTIONS]
    jumped = next((h for h, prev, cur in zip(
        INGEST_REPORT_SECTIONS[1:], seen, seen[1:]) if cur < prev), "")
    return "" if not jumped else (
        f"Ingest.report has `{jumped}` out of order — the four headings "
        f"must appear in this order: {order}")


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
                    f"give that brick a `Uses: {decision.target_id}` line "
                    f"instead, and its Theorem and Proof reach the worker "
                    f"that declares a sub-goal of that name. If a PRIOR "
                    f"batch was to mint it: that mint died before creating "
                    f"the goal (check its outcome in `## Completed Inject "
                    f"batches`) — re-mint it rather than target it. "
                    f"Otherwise use the integer goal id shown in "
                    f"Context.md's active goal list")
        decision.target_id = int(row["id"])

    if k == "Inject":
        # Shape-derived mode (update_plan_2026_07 #1): `target_goal_id`
        # present → work that goal (the Formalizer decides prove-vs-
        # split itself — steer with the brick's mathematics, not a
        # mode); absent → mint ONE new brick. The legacy `pipeline`
        # payload field is ignored when present.
        #
        # Named bricks (owner ruling 2026-09-07): an Inject NAMES a brick
        # of this batch's `## Proof`; it no longer carries a copy of it.
        # A decision that still carries `proof` is REJECTED rather than
        # aliased — silently accepting the copy is how the two texts
        # drift, and drift here means the worker formalizes an argument
        # the judge never read.
        if isinstance(decision.brief, str) and decision.brief.strip():
            return (
                "Inject no longer carries `proof`: name the brick "
                "instead — `{\"kind\": \"Inject\", \"brick\": \"<name>\"}`. "
                "Every brick of your `## Proof` opens with a "
                "`### <name>` header, and that name is what an Inject "
                "names (and what the node is called). Delete the `proof` "
                "field.")
        name = brick_name_of(decision)
        if not name:
            return ("Inject requires `brick` (string): the name of a "
                    "brick in this batch's `## Proof`. Each brick there "
                    "opens with `### <name>`; the Inject names one of "
                    "them, and the worker formalizes that brick's "
                    "`Theorem.` against its `Proof.`")
        defect = _programme._name_defect(name, "Inject `brick`")
        if defect:
            return defect
        if (decision.payload.get("briefs") or decision.payload.get("directive")
                or decision.payload.get("brief")):
            return (f"Inject schema uses top-level `brick: str`; "
                    f"`brief` / `briefs` / `directive` fields are legacy "
                    f"— remove them and name the brick with `brick`")
        target = decision.target_id
        if target is None:
            # Mint shape. The brick's name IS the declaration's name, so
            # a name already taken in this problem is a landing-time
            # hard failure — checked here instead, before the worker
            # spends its budget on a brick that cannot commit.
            taken = conn.execute(
                "SELECT id, status FROM goals WHERE problem = ? AND slug = ?",
                (problem, name)).fetchone()
            if taken is not None:
                return (f"Inject `brick`: name `{name}` is taken by "
                        f"g{taken['id']} ({taken['status']}) — a mint "
                        f"lands as `theorem {name}` in "
                        f"`proofs/L_{name}.lean` and that name already "
                        f"exists. Target it "
                        f"(`\"target_goal_id\": \"{name}\"`), or pick "
                        f"another name for the brick.")
            if workspace is not None:
                landed = (db.problem_dir(Path(workspace), problem)
                          / "proofs" / f"L_{name}.lean")
                if landed.exists():
                    return (f"Inject `brick`: `proofs/L_{name}.lean` "
                            f"already exists — a mint under that name "
                            f"cannot commit. Cite the landed brick and "
                            f"pick another name for this one.")
            return ""
        g = db.get_goal(conn, int(target))
        if g is None:
            return f"target_goal_id={target} not found"
        if str(g["problem"]) != problem:
            return (f"target goal belongs to problem "
                    f"{g['problem']!r}, not {problem!r}")
        if str(g["status"]) == "proved":
            return (f"target_goal_id={target} is 'proved'; Inject cannot "
                    f"redispatch a finished proof. Open a different angle "
                    f"on a different goal instead.")
        # 2026-09-04 (owner ruling): `disproved` is REFUSED here. The
        # 08-18 opening treated the mark as a claimed counterexample an
        # Inject could argue away; the disproof gate has landed since,
        # so the mark is a kernel-certified refutation and re-arguing it
        # is exactly the move the gate exists to end. The teaching line
        # names the reachable action — a refutation is escaped by a
        # DIFFERENT statement, not a louder proof of the same one.
        if str(g["status"]) == "disproved":
            return (
                f"Inject rejected: goal {target} is 'disproved' — the "
                f"kernel checked a counterexample, so the statement is "
                f"false and no argument revives it. Mint a NEW statement "
                f"that survives that counterexample (Inject with no "
                f"target, stating the corrected claim), or ConfirmShelve "
                f"the line. If you believe the refutation itself is "
                f"wrong, say so in your Roadmap: undoing a kernel "
                f"verdict is an operator repair, not a decision."
            )
        # Ancestor safety walk (was Reopen's responsibility pre-2026-05-28;
        # now the goal-targeted Inject takes over as the unified
        # reactivation mechanism). A `disproved` ancestor means a
        # counterexample already stands against a parent statement, so
        # this descendant is moot; commit's auto-detach handles parked
        # chains, which do not block.
        bad, anc_kind = _dispatcher._has_hard_terminal_ancestor(
            conn, int(target))
        if bad:
            return (
                f"Inject rejected: goal {target} has a "
                f"'disproved' ancestor (the kernel checked a "
                f"counterexample for a parent statement, so this "
                f"descendant is moot as long as that stands). Re-cut the "
                f"line from a NEW statement that survives it, or "
                f"ConfirmShelve this one."
            )
        # Target mode: the brick's name IS the goal's slug (owner ruling
        # 2026-09-07). The name is the node's identity — a brick called
        # something else names a different node, and the worker would be
        # handed an argument addressed to nobody.
        if name != str(g["slug"]):
            return (f"Inject `brick`: the brick for g{g['id']} must be "
                    f"named `{g['slug']}` — a brick's name IS its node's "
                    f"name, and this Inject targets that goal. Rename the "
                    f"`### {name}` header to `### {g['slug']}`.")
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
        # (the same reason task #112's dead-twin gate misfired; that gate
        # is retired, 2026-09-04).
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
            # Proved is necessary, not sufficient (2026-08-30): the node
            # must be the brick the disproof gate minted — `<slug>_disproof`
            # beside a `disproved` <slug>. A hand-minted negation has no
            # kernel link to the claim it says it refutes.
            from .._disprove import refuted_goal_for
            if refuted_goal_for(conn, int(g["id"])) is None:
                return (f"ReturnToParent(refuted) target g{g['id']} "
                        f"`{g['slug']}` is not a disproof-gate brick. "
                        f"Inject the node you hold false, with the "
                        f"counterexample as its brick's `Proof.`; the "
                        f"worker certifies the negation and "
                        f"`<slug>_disproof` lands — name that node here")
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

    if k == "Theorize":
        # theory_wake_design.md §2. Two fields, and each one is a
        # question the author cannot answer without: the objective says
        # what would SUFFICE (a statement whose proof or refutation
        # moves the claim, or the wall to be crossed), the situation
        # says where the record already stands. A request without the
        # second makes the Theorist re-derive what is landed and hand
        # back the record in new words — the failure the reviewer's
        # first criterion exists to catch, bought a whole pipeline
        # earlier and cheaper here.
        for field, what in (
                ("objective", "the statement whose proof or refutation "
                              "would move the claim, or the wall to be "
                              "crossed"),
                ("situation", "where the record stands — what has "
                              "landed, what died and why, what is "
                              "parked, with pointers (goal ids, dead "
                              "attempts, PAST lines)")):
            v = decision.payload.get(field)
            if not isinstance(v, str) or not v.strip():
                return (f"Theorize requires non-empty `{field}` "
                        f"(string): {what}")
        # ONE wall at a time (design §2). Not a style rule: the theory
        # layer is a seat pair with its own quota, and a group that can
        # ask three questions at once spends the layer on breadth while
        # the wall it is actually stopped at waits its turn.
        me = _authoring_group(conn, problem, group_id)
        open_row = conn.execute(
            "SELECT id FROM strategist_decisions"
            " WHERE problem = ? AND decision_kind = 'Theorize'"
            "   AND outcome IS NULL"
            + ("" if me is None else " AND group_id = ?")
            + " LIMIT 1",
            (problem,) if me is None else (problem, int(me["id"])),
        ).fetchone()
        if open_row is not None:
            return (
                f"a Theorize of yours is already in flight (decision "
                f"#{int(open_row['id'])}) — one per group at a time. "
                f"Its document comes back as a batch outcome; wait for "
                f"it, or ask a different question next batch. If the "
                f"wall has moved since, that is what the NEXT request's "
                f"`situation` is for.")
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
        return ("AttemptDisproof is retired — `Inject` the node you hold "
                "false with the counterexample in `proof`; the worker "
                "certifies the negation in the kernel and `<slug>_disproof` "
                "lands. A sub-group then hands its charter back via "
                "`ReturnToParent(refuted)` naming that node; a disproved "
                "root exits through `Ingest` (the problem closes as "
                "`refuted`)")

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
        # A root settled either way is a deliverable: proved closes the
        # problem as ingested, disproved (the gate's `<slug>_disproof`
        # beside it) as refuted — owner ruling 2026-08-30.
        root_proved = (root is not None and str(root["status"])
                       in transitions.GOAL_HARD_TERMINALS)
        if root is not None and not root_proved:
            return ("Ingest is blocked: this problem has a root goal "
                    f"(status={root['status']!r}) that must be proved "
                    "— or kernel-disproved — before the terminal "
                    "judgment is valid")
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
        from ...state import proof_store as _proof_store
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
        #
        # Last, on purpose: the mechanical blockers above name work that
        # must happen before the terminal is even arguable, and asking
        # for the write-up first would put the report ahead of the proof.
        defect = _ingest_report_defect(
            str(decision.payload.get("report") or ""))
        if defect:
            return defect
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


#: Goal statuses a `Uses:` name may resolve to when it names an EXISTING
#: node rather than a brick of this batch. Parked and settled-false nodes
#: are refused by name: an argument that leans on one leans on work
#: nobody is doing, and the author is the only reader who can say what to
#: do about it.
_USES_LIVE_STATUSES = frozenset({"open", "attempting", "proved"})


def verify_injects(decisions: "list[Decision]",
                   bricks: "list[_programme.Brick]",
                   conn: sqlite3.Connection, *, problem: str) -> str:
    """The checks that need this batch's `## Proof` AND the record.

    Runs after `verify_proposal_package` has parsed the proposal, so the
    per-decision gate (which also serves callers with no proposal at all)
    stays shape-only. Returns '' or one teaching message.

    Rules (owner ruling 2026-09-07):
      1. every `Inject.brick` names a brick of THIS batch's `## Proof`;
      2. a brick another brick lists under `Uses:` is NOT injected — it
         reaches the worker that declares a sub-goal of that name;
      3. every `Uses:` name resolves to a same-batch brick or to a live
         or proved goal of this problem.
    (The mint-collision and target-slug rules are per-decision — they
    need no proposal — and live in `verify_decision`.)"""
    by_name = {b.name: b for b in bricks}
    used_by: "dict[str, list[str]]" = {}
    for b in bricks:
        for u in b.uses:
            used_by.setdefault(u, []).append(b.name)
    roster = (", ".join(f"`{b.name}`" for b in bricks)
              or "(the `## Proof` names none)")
    for i, d in enumerate(decisions):
        if d.kind != "Inject":
            continue
        name = brick_name_of(d)
        if name not in by_name:
            return (f"decision #{i}: Inject `brick`: `{name}` is not a "
                    f"brick of this batch's `## Proof`. Every brick there "
                    f"opens with a `### <name>` header; this Proof's "
                    f"bricks are {roster}. Name one of them, or add the "
                    f"brick you meant to inject.")
        if name in used_by:
            others = ", ".join(f"`{o}`" for o in used_by[name])
            return (f"decision #{i}: `{name}` is used by {others}; it is "
                    f"not injected — its Theorem and Proof reach the "
                    f"worker that declares a sub-goal named `{name}`, at "
                    f"any depth. Inject {others} instead.")
    for b in bricks:
        for u in b.uses:
            if u in by_name:
                continue
            g = conn.execute(
                "SELECT id, status FROM goals WHERE problem = ? AND slug = ?"
                " ORDER BY id DESC LIMIT 1", (problem, u)).fetchone()
            if g is None:
                return (f"brick `{b.name}` lists `Uses: {u}`, but `{u}` is "
                        f"neither a brick of this `## Proof` ({roster}) nor "
                        f"a node of this problem — nothing carries an "
                        f"argument for it. Add a `### {u}` brick, or drop "
                        f"it from the `Uses:` line.")
            if str(g["status"]) not in _USES_LIVE_STATUSES:
                return (f"brick `{b.name}` lists `Uses: {u}`, but g{g['id']} "
                        f"`{u}` is {g['status']} — an argument cannot lean "
                        f"on a node nobody is working. Revive it with an "
                        f"`Inject(target_goal_id=\"{u}\")`, write a `### {u}` "
                        f"brick that replaces it, or drop it from the "
                        f"`Uses:` line.")
    return ""


def verify_decisions(decisions: list[Decision], conn: sqlite3.Connection,
                     *, problem: str,
                     workspace: "Path | None" = None,
                     trigger_kind: str = "",
                     group_id: "int | None" = None) -> str:
    """Validate a multi-decision batch. Runs `verify_decision` on each
    item in declared order, then applies the cross-decision invariants
    that only matter when several decisions land in the same call —
    `batch_rules.cross_decision_refusals`, composed by
    `batch_rules.compose`.

    Returns '' if all pass, otherwise EVERY per-decision failure in one
    message. Caller must abort the commit when this returns non-empty —
    `commit_decisions` assumes verify passed.

    It used to stop at the first one, so a batch with three defects cost
    three wakes to learn three sentences the verifier already knew on
    the first pass (08-13 strategist report). The author cannot see
    these checks; the round trip is the only channel, and metering it
    one rejection at a time is the framework charging for its own
    silence. Cross-decision checks still run only on a clean set —
    their premise is that each decision is individually valid — and
    since 2026-09-08 they are collected the same way: several batch
    rules refusing at once is exactly when one at a time cannot work,
    because a rule's remedy can be the shape the next rule refuses
    (p617, this module's `batch_rules` docstring).
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

    # Cross-decision rules (`batch_rules`): collected, never returned
    # one at a time. Their remedies do not always compose — the p617
    # cascade / review-discharge pair on 2026-09-08 each prescribed a
    # shape the other refused — so the batch verifier asks for ALL of
    # them and composes one answer naming a shape that satisfies every
    # one (or saying they conflict, and which decision resolves it).
    refusals = _batch_rules.cross_decision_refusals(
        decisions, conn, problem=problem, trigger_kind=trigger_kind,
        group_id=group_id)
    return _batch_rules.compose(decisions, refusals, conn, problem=problem,
                                trigger_kind=trigger_kind, group_id=group_id)
