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

from .model import BATCH_DONE_LIKE, Decision, RETURN_FLAVOURS


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
#: (`Ingest.report` → `problems.ingest_report` → `REPORT.md`). The gate
#: is written and tested in both positions NOW and armed LATER: the
#: wording that asks for the field is staged in
#: `Tooling/prompts/_staged/hid_prompt_changes.md` and is not live, and a
#: gate that refuses a field the Strategist was never asked for teaches
#: nothing — it just burns the wake. Flip to True in the same commit that
#: moves that wording into the live prompts.
INGEST_REPORT_REQUIRED = False

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
            return ("Inject requires non-empty `proof` (string): this "
                    "brick's `Theorem.` statement and `Proof.` argument, "
                    "copied from this batch's `## Proof` with the "
                    "vocabulary it uses")
        # The two-part brick (owner ruling 2026-08-30): the statement is
        # a structural position — the mint worker's assignment, the
        # judge's unit — so its presence is checked here, its truth is
        # not (that reader is the worker, via `return_to_nl`).
        _, _, _, shape_err = _programme.parse_brick_proof(decision.brief)
        if shape_err:
            return f"Inject `proof`: {shape_err}"
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
            # Proved is necessary, not sufficient (2026-08-30): the node
            # must be the brick the disproof gate minted — `<slug>_disproof`
            # beside a `disproved` <slug>. A hand-minted negation has no
            # kernel link to the claim it says it refutes.
            from .._disprove import refuted_goal_for
            if refuted_goal_for(conn, int(g["id"])) is None:
                return (f"ReturnToParent(refuted) target g{g['id']} "
                        f"`{g['slug']}` is not a disproof-gate brick. "
                        f"Inject the node you hold false with the "
                        f"counterexample in `proof`; the worker certifies "
                        f"the negation and `<slug>_disproof` lands — name "
                        f"that node here")
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
        root_proved = root is not None and str(root["status"]) in (
            "proved", "disproved")
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
        if INGEST_REPORT_REQUIRED:
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
                # proved / dead by another path) is not a line this batch
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
                return (
                    f"routine audit {int(pending['id'])} fired on lines "
                    f"this batch leaves untouched:\n{lines}\n"
                    f"Act on every fired root: `ConfirmShelve` it (its "
                    f"restart condition in the Roadmap's PAST) or "
                    f"`Inject(target_goal_id=...)` it with the argument "
                    f"that keeps it. Other decisions may accompany these.")

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
                    "wrongness. `Noop` may accompany, never alone."
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


