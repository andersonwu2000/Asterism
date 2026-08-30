"""Strategist context compilation — trigger/axiom/ingest-gate/disproof/
stall sections, the roster/replay/plan-note/directive/tree/charter
family, and `compile_strategist_context` itself (the Phase 2 entry that
assembles Context.md for the Strategist agent).

Split out of `phase2_context.py` 2026-08-28 (Phase B, B2) unchanged.
`_CATALOG_RECENT_N` stays here — the catalog-index section that gives
it meaning (`_section_catalog_index_strategist`) is Strategist-side;
`forward.py`'s `_section_library_inventory` imports it back.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ...state import db
from ...state import intent as intent_mod
from .. import context

from .dossier import (
    _section_pending_review_failure,
    _section_pending_review_adjudications,
    _section_pending_review_strategies,
    _section_pending_review_ancestors,
)
from .outcomes import (
    _section_inject_batch_outcomes,
    _section_pending_reopens,
    _prose_label,
)

# Inline tail of the proved catalog (strategist index + Forward
# library): the freshness floor against a stale plan note / brief.
# Full list lives in the CATALOG.md companion.
_CATALOG_RECENT_N = 25


def _section_trigger(trigger_kind: str, pending_review_id: int | None,
                     conn: sqlite3.Connection,
                     workspace: Path) -> list[str]:
    lines = [
        "## Trigger",
        "",
        f"`trigger_kind`: {trigger_kind}",
        "",
    ]
    if trigger_kind == "pending_review" and pending_review_id is not None:
        g = db.get_goal(conn, pending_review_id)
        if g is not None:
            lines += [
                f"Pending review on goal {pending_review_id}:",
                "",
                f"- slug: `{g['slug']}`",
                f"- statement: `{context.goal_display_signature(workspace, str(g['slug']), g['lean_path'], g['statement'])}`",
                f"- depth: {g['depth']}",
                f"- attempts: {g['attempts']}",
                "",
            ]
    return lines


def _axiom_certification_note(conn: sqlite3.Connection,
                              intent: "intent_mod.ProblemIntent | None",
                              problem: str) -> list[str]:
    """What the machine already checked about axioms, rendered exactly
    when `Ingest` becomes reachable (2026-08-02 feedback).

    The problem's axiom whitelist states the obligation explicitly, but `.lake/build`
    is outside the Strategist's readable roots, so the one wake that has
    to certify it could only argue it by grepping sources for `sorry` and
    left a `SUSPECT:` line on its own exit gate. The probe it wanted to
    run has ALREADY run: `#print axioms <= whitelist` is the definition of
    `goals.status='proved'` here, not a later audit (`pipeline/_axiom.py`;
    `tests/test_axiom_invariant.py` pins every proved-producing pipeline
    to the shared gate). Stating that turns a hand-argued obligation into
    a citable machine fact — the Strategist is not being asked to
    re-adjudicate a kernel gate."""
    n = conn.execute(
        "SELECT COUNT(*) FROM goals WHERE problem = ? AND status = 'proved'",
        (problem,)).fetchone()[0]
    if not n:
        return []
    wl = (intent_mod.effective_axioms(intent, problem=problem)
          if intent is not None else [])
    wl_txt = ", ".join(f"`{a}`" for a in wl) if wl else "(none listed)"
    return [
        "## Axiom certification (already machine-checked)",
        "",
        f"All {n} goal(s) this problem shows as `proved` cleared "
        f"`#print axioms` against its whitelist before the status flipped "
        f"— that gate IS the definition of `proved`, and `sorryAx` can "
        f"never be whitelisted. In force: {wl_txt}.",
        "",
        "Cite this for `Ingest`'s axiom obligation. You have no"
        " `.lake/build` access and are not expected to re-run the probe.",
        "",
    ]


def _section_ingest_gate(conn: sqlite3.Connection,
                         problem: str,
                         group_id: "int | None" = None,
                         intent: "intent_mod.ProblemIntent | None" = None,
                         ) -> list[str]:
    """Phase 6 — context-conditional Ingest availability note (design ④):

      - root exists, NOT proved → surface "Ingest is unavailable" (the
        HARD gate would reject it), so the Strategist doesn't burn a
        decision on it.
      - root not proved → also state the ordering cost: a citer
        dispatched before its citees land cannot read their exact
        statements from CATALOG.md (ungated 2026-07-30; the old
        `frozen`-only gate meant it never rendered).
      - root proved, or no root (pure-NL) → say nothing; the prompt's
        standing instruction ("commit Ingest once the charter's
        requirements are met") is the only voice — these notes would be
        pure noise once they stop being true.
    """
    # v35 — a SUB-group's exit is gated on ITS anchor (or its own marked
    # deliverables), never on the problem's root. Told otherwise, every
    # sub-group of a rooted problem is informed on every wake that Ingest
    # is unavailable, never delivers, and its parent's `Delegate` stays
    # NULL forever — the parent then waits in silence for good.
    from ...state import groups as _groups
    me = _groups.get(conn, int(group_id)) if group_id is not None else None
    if me is not None and not _groups.is_top(me):
        anchor = me["anchor_goal_id"]
        if anchor is None:
            return []
        g = db.get_goal(conn, int(anchor))
        if g is None or str(g["status"]) == "proved":
            return []
        return [
            "## Ingest availability",
            "",
            f"`Ingest` is unavailable — this group's anchor g{anchor} is "
            f"not yet proved (status: `{g['status']}`). Settle it, or "
            f"hand the charter back with `ReturnToParent`.",
            "",
        ]
    root = conn.execute(
        "SELECT status FROM goals WHERE problem = ? AND origin = 'root'"
        " LIMIT 1", (problem,)).fetchone()
    if root is None or str(root["status"]) == "proved":
        return _axiom_certification_note(conn, intent, problem)
    lines = [
        "## Ingest availability",
        "",
        f"`Ingest` is unavailable — the root goal is not yet proved "
        f"(status: `{root['status']}`; hard exit gate).",
        "",
    ]
    # Ordering advice, ungated (2026-07-30): it used to render only for
    # a `frozen` root, i.e. almost never, and its old wording forbade a
    # same-batch root Inject — obsolete since #123 made that legal (the
    # commit gate registers a wait edge). What survives is the real
    # cost: a citer dispatched before its citees land cannot read their
    # exact statements from CATALOG.md and has to assume the shape.
    lines += [
        "Land a goal's cited prerequisites before dispatching it; if"
        " you dispatch first, pin their exact signatures in the brief.",
        "",
    ]
    return lines


def _section_disproof_guidance(conn: sqlite3.Connection,
                               problem: str) -> list[str]:
    """Context-conditional falsity triage. Rendered only when the
    problem shows falsity signals (a `disproved` goal), so healthy
    problems never see it (prompt stays static). AttemptDisproof
    retired 2026-08-04 — the bet is expressed with a negation mint.
    """
    signals = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM goals WHERE problem = ? AND"
        "  status = 'disproved')", (problem,)).fetchone()[0]
    if not signals:
        return []
    return [
        "## Falsity triage",
        "",
        "A goal here is believed false. Triage before spending:",
        "- Looks like a USER TYPO (sign/bound/quantifier plainly "
        "misstated) → `RequestUserAmend` with the suggested fix; don't "
        "burn compute disproving a typo.",
        "- STRUCTURAL doubt about a claim (counterexample sketch, "
        "failing special case) → `Inject` a Forward mint stating the "
        "precise negation or the counterexample; the kernel settles "
        "it, not belief. A kernel-settled disproof of a USER claim "
        "goes back via `RequestUserAmend` — never `Ingest` over it.",
        "- Merely HARD → keep proving; difficulty is not falsity.",
        "- Inner (non-deliverable) sub-goals believed false usually "
        "mean the DECOMPOSITION is wrong — re-decompose, don't disprove.",
        "",
    ]


def _section_stall_warning(conn: sqlite3.Connection,
                           problem: str,
                           group_id: "int | None" = None) -> list[str]:
    """Structural stall detection (B-2 fix).

    Surfaces a header when:
      - `Ingest` not yet committed AND
      - zero open goals reachable AND
      - no in-flight worker.

    These conditions mean BFS literally cannot dispatch anything until
    Strategist intervenes. Polar 2026-05-23 hit this for 174 min while
    Strategist routine-Noop'd 4 times reading the unchanging "X proved"
    snapshot. With this header surfaced, Strategist sees the structural
    deadlock signal directly; prompt rule (`strategist.md`) requires
    non-Noop when this section is present.

    Re-checks the same signal that `dispatcher.strategist_triggers` T4
    uses to enqueue; safe to compute redundantly here at context-
    compile time (the queue enqueue may pre-date the actual Strategist
    spawn by seconds, during which a parallel goal could land —
    re-checking ensures the warning reflects current state)."""
    # Single source of truth for the stall signal — `db.is_problem_stalled`
    # (also drives T4's `db.problems_stalled`). The two MUST agree: a
    # divergence (e.g. raw vs reachable open-goal counting) makes T4 fire a
    # Strategist whose context then shows NO stall warning, so it
    # Noop-confirms, re-stalls, and T4 re-fires → a Strategist livelock
    # (P13 2026-06-13). Context-compile owns no in-memory `running` set, so
    # this is a queue-only in-flight check (a worker mid-spawn briefly
    # suppresses the warning — harmless; the next compile re-checks).
    # v35 — T4 detects a stall PER GROUP, so this must ask the same
    # question of the same group. Left problem-wide it recreates the P13
    # livelock exactly: a stalled sub-group is woken by T4, sees no stall
    # warning, Noops, gets rejected by the advance gate, and T4 fires
    # again.
    stalled = (db.is_group_stalled(conn, problem, group_id)
               if group_id is not None
               else db.is_problem_stalled(conn, problem))
    if not stalled:
        return []
    # WHOSE deadlock. `is_group_stalled` answers for this group, and the
    # flat "no worker is in flight" then contradicted `## Dispatched,
    # still running` — problem-wide — in the same compile of the same
    # file. Seventeen agents spent rounds reconciling two true
    # sentences (2026-08-15/16); one asked for exactly this: "label
    # execution-state sections explicitly as group-local or
    # problem-global".
    whose = ("no worker of this group's is in flight"
             if group_id is not None else "no worker is in flight")
    scope = "this group" if group_id is not None else "this problem"
    return [
        "## Framework stalled",
        "",
        "Structural deadlock detected: this problem has not been"
        " `Ingest`ed, no `open` goal is reachable for BFS dispatch, and"
        f" {whose}. The framework"
        f" cannot dispatch any worker on {scope} until you intervene.",
        "",
        "Typical causes:",
        "",
        "- The problem is FRESH — nothing has been injected yet; your"
        " job is to commit the first Inject batch from your charter.",
        "- Everything you planned is proved and the charter's"
        " requirements are met — commit `Ingest` to close the problem.",
        "- A parent strategy has a `shelved` sub-goal — the strategy"
        " stays `proposed` waiting for the sub-goal to be re-dispatched"
        " but no automatic trigger fires.",
        "- A `pending_strategist_review` goal blocks dispatch through"
        " its ancestor chain.",
        "- All live strategies have a missing prerequisite that no"
        " current Forward batch is addressing.",
        "",
        "**`Noop` is not appropriate while this section is present.**"
        " Choose one of: `Inject(target_goal_id=..., proof=...)`"
        " (work a `shelved` / `pending_strategist_review` / `frozen`"
        " goal — `frozen` is the root before its first launch, and it"
        " is the only dispatch path to it), a"
        " no-target `Inject` (mint the missing prerequisite), `Ingest` (every charter requirement is"
        " satisfied — the terminal judgment), `ConfirmShelve` (truly"
        " cannot proceed — followed by an Inject that pivots), or"
        " `RequestUserAmend` (a user file needs fixing).",
        "",
    ]


_ACTIVE_GOALS_TAIL_N = 15

#: Full review dossiers inlined per wake; the rest get one line + the
#: lazy companions (a wake with many waiting goals must still fit the
#: window — 能懶載入的東西不需要 cap 的例外是「必須全文的」前幾個).
_REVIEW_DOSSIER_CAP = 3


def _section_active_goals(conn: sqlite3.Connection,
                          workspace: Path,
                          problem: str) -> list[str]:
    # Status-based filter: any non-terminal status (open / attempting /
    # pending_strategist_review). Descendants of a shelved / disproved
    # ancestor are cascade-shelved at the data layer by
    # `dispatcher._cascade_shelve_descendants`, so they drop out of
    # this status filter naturally. No view-level alive-set CTE needed:
    # the goal status IS the source of truth for "is this dispatchable".
    rows = list(conn.execute(
        "SELECT id, slug, statement, lean_path, depth, status, attempts"
        " FROM goals WHERE problem = ?"
        "   AND status IN ('open','attempting','pending_strategist_review')"
        " ORDER BY depth, id",
        (problem,),
    ))
    if not rows:
        return []
    # INDEX EAGER, SIGNATURES LAZY (2026-08-10).
    #
    # This section existed to stop a spawn restating a goal that is
    # already alive, and it carried each goal's FULL signature to make
    # the comparison possible inline. Measured across today's renders it
    # was 16,557B of a 39,000B Context — 42% — and the signatures are
    # ~90% of that. Every one of those bytes is re-sent on EVERY step of
    # the agent loop, not once per spawn.
    #
    # What changed is that the signature now has a cheap on-demand
    # source: `inspect([{"decl": "<slug>"}])` answers from the goals
    # table — statement, file and status — and did not exist until this
    # morning. So the list stays COMPLETE (the agent still sees exactly
    # what is alive, which is what prevents the restatement) while the
    # bytes that only matter when comparing one specific pair move to
    # the moment of comparison.
    #
    # Not a truncation: nothing is silently dropped and the pointer says
    # how to get the rest (#177's rule — a cap that hides itself is the
    # thing that rule forbids). And duplicate-avoidance is not left to
    # goodwill either way: `quality/dedupe.py` enforces it mechanically
    # at commit, tier-0 and defeq. This section is the courtesy that
    # saves a spawn, not the gate.
    # The staleness caveat mirrors `## TREE`'s (2026-08-15) — the
    # 08-15 fix covered one of two isomorphic status lists and the
    # other became the dominant "surfaces disagree" feedback pair
    # (~83 entries, autopsy 2026-08-24): statuses here are frozen at
    # compile time while workers keep landing proofs.
    counts: "dict[str, int]" = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    count_line = " / ".join(f"{n} {s}" for s, n in
                            sorted(counts.items(), key=lambda kv: -kv[1]))
    out = ["## Active goals", "",
           f"**{len(rows)} alive** — {count_line}",
           "",
           "_Statuses frozen at compile time — they move while you "
           "work. Before deciding anything from one, ask the record "
           "live: `inspect([{\"decl\": \"<slug>\"}])` (also returns "
           "the statement and file)._",
           ""]
    # Index eager was right (2026-08-10); FULL roster inline was not
    # (user backlog item d, 2026-08-26): on a mature problem this was
    # ~80 lines re-sent on EVERY loop step, while the same roster —
    # with full signatures — is machine-written into CATALOG.md's
    # `## Alive goals` beside this Context each wake. Freshness floor
    # stays inline (the newest goals are the ones a stale plan note
    # contradicts); the rest is one grep away, and dedupe at commit is
    # the real gate either way.
    tail = sorted(rows, key=lambda r: int(r["id"]))[-_ACTIVE_GOALS_TAIL_N:]
    if len(rows) > len(tail):
        out.append(f"_The {len(tail)} newest (full roster with "
                   f"signatures: `CATALOG.md` § `Alive goals`, beside "
                   f"this file — grep it by slug):_")
    for r in tail:
        out.append(
            f"- [{r['id']}] depth={r['depth']} "
            f"{r['status']:25s} attempts={r['attempts']}"
            f" `{r['slug']}`"
        )
    out.append("")
    return out


# Longest `outcome_detail` on record is ~1.3 KB (a decline's prose) and
# this section renders 5 rows, most carrying none — so the budget is
# generous enough that nothing real gets cut, and bounded so one verbose
# decline cannot own the section.
_REPLAY_DETAIL_BUDGET = 800


def _section_failure_replay(conn: sqlite3.Connection,
                            problem: str,
                            k: int = 5) -> list[str]:
    """Last `k` strategist_decisions on this problem with their
    outcomes — self-feedback signal so Strategist learns
    'what I tried, what happened'."""
    try:
        rows = list(conn.execute(
            "SELECT triggered_at_tick, trigger_kind, decision_kind,"
            " target_id, brief, reason, payload, outcome, outcome_detail,"
            " created_at"
            " FROM strategist_decisions WHERE problem = ?"
            " ORDER BY id DESC LIMIT ?",
            (problem, k),
        ))
    except sqlite3.OperationalError:
        return []
    if not rows:
        return ["## Recent decisions", "", "(none — first Strategist run)", ""]
    out = ["## Recent decisions (newest first)", ""]
    for r in rows:
        out.append(
            f"- tick={r['triggered_at_tick']} "
            f"trigger={r['trigger_kind']} → "
            f"`{r['decision_kind']}`"
            + (f" target={r['target_id']}" if r['target_id'] else "")
            + (f" outcome={r['outcome']}" if r['outcome']
               else "  [IN FLIGHT — dispatched, no result yet]")
        )
        if r["reason"]:
            reason = str(r["reason"])
            if len(reason) > 200:
                reason = reason[:200] + "…"
            out.append(f"  reason: {reason}")
        if r["brief"]:
            brief = str(r["brief"])
            if len(brief) > 200:
                brief = brief[:200] + "…"
            out.append(f"  {_prose_label(r['decision_kind'])}: {brief}")
        # A decision's WHY, whenever one was recorded — the test is
        # "is there anything to say", not "is the outcome named
        # `failed:`". Only that one family follows the prefix
        # convention, so an outcome-name test mutes every other kind
        # that carries detail: measured 2026-08-14, 36 rows silent, of
        # which 17 were `paper_unfetchable` holding the whole Scholar
        # report (identity resolved, DOI, why no whitelisted copy
        # exists, the URL a human can open). The comment this replaces
        # named FetchPaper as the case it existed for. A group read the
        # resulting silence as "the fetch never ran", flagged its own
        # correct record SUSPECT, and planned to spend another batch
        # re-fetching a paper already ruled unfetchable.
        detail = " ".join(str(r["outcome_detail"] or "").split())
        if detail:
            # Elide the middle, never the tail. Scholar puts the
            # actionable half LAST — why it cannot be fetched, and
            # where a human can read it — so a head truncation hides
            # exactly the part that changes the next decision. There is
            # no companion file behind this section to fall back on.
            if len(detail) > _REPLAY_DETAIL_BUDGET:
                half = _REPLAY_DETAIL_BUDGET // 2
                detail = f"{detail[:half]} …… {detail[-half:]}"
            out.append(f"  why: {detail}")
    out.append("")
    return out


def _plan_note_provenance(conn: sqlite3.Connection, problem: str,
                          group_id: "int | None" = None) -> str:
    """The framework's own record of what the last wake actually landed:
    last committed batch id + current Programme rev.

    The note is persisted right after the spawn — BEFORE the package
    gate, the Adversary and the commit decide whether that batch ships
    (deliberate: the note is the agent's memory of its own thinking and
    is worth keeping even when the wake then fails). So a discarded
    batch leaves a note asserting a state the framework never entered.
    Two SG wakes (07-29) each burned on forensics reconstructing that,
    and the agent's workaround was a standing "do not trust your own
    prior plan note" rule. Stamping the render — not the file — keeps
    the check crash-proof (a killed wake writes no footer) and immune
    to the agent's own rewrites."""
    from ...state import programme as _programme
    # v35 — the plan note is per group, so its provenance line must be
    # too: a sub-group Strategist stamped with the TOP group's last
    # batch + rev count would read every one of its own wakes as a
    # phantom batch (#164 class). group_id=None keeps the problem-wide
    # read for pre-v35 rows.
    q = ("SELECT batch_id, created_at FROM strategist_decisions"
         " WHERE problem = ? AND batch_id IS NOT NULL")
    args: tuple = (problem,)
    if group_id is not None:
        q += " AND group_id = ?"
        args = (problem, int(group_id))
    row = conn.execute(q + " ORDER BY id DESC LIMIT 1", args).fetchone()
    rev = _programme.current_rev(conn, problem, group_id)
    rev_txt = (f"Programme rev {rev['rev']}" if rev is not None
               else "no Programme rev")
    if row is None:
        return f"_Framework: no batch committed · {rev_txt}._"
    return (f"_Framework: last committed batch `{row['batch_id']}` · "
            f"{rev_txt} · {str(row['created_at'])[:16]}._")


PLAN_NOTE_COMPANION = "_plan_full.md"


def _section_plan_note(conn: sqlite3.Connection, workspace: Path,
                       problem: str,
                       group_id: "int | None" = None,
                       attempts_dir: "Path | None" = None) -> list[str]:
    """The Strategist's PRIVATE cross-wake plan note
    (`.drafts/strategist_plan.md`) — rendered here ONLY, never into worker
    contexts. The third channel next to the two worker-facing ones
    (standing directive broadcast / one-shot Inject brief): its curated
    world-model previously leaked into the directive and taxed every
    worker spawn.

    Lazy since 2026-08-04 (operator ruling; #2 context growth source at
    ~6-10KB and climbing toward the 16KB soft cap): the full note rides
    beside Context.md as `_plan_full.md` — the same pattern as
    `BATCHES.md`/`CATALOG.md` — and the inline render keeps only what
    cannot wait for a Read: the provenance line (the phantom-batch
    two-line compare) and the `SUSPECT:` lines (adjudicate-first duty).
    The REWRITE contract is unaffected: the agent Reads the companion,
    then writes the fresh `_plan.md` as always.

    Rendered under `_plan_note_provenance` — the framework's line on
    what actually committed, so a phantom batch is a two-line compare
    instead of an archaeology session."""
    from ...pipeline import _drafts
    problem_dir = db.problem_dir(workspace, problem)
    text = _drafts.read_plan_note(problem_dir, group_id)
    if not text or not text.strip():
        return []
    out = ["## Your plan note (private, cross-wake)", "",
           _plan_note_provenance(conn, problem, group_id), ""]
    if len(text) > _drafts.PLAN_NOTE_SOFT_CAP:
        out += [f"_⚠ {len(text)} chars — past the useful size; rewrite it "
                f"down to what still matters._", ""]
    lazy = False
    if attempts_dir is not None:
        try:
            (attempts_dir / PLAN_NOTE_COMPANION).write_text(
                text, encoding="utf-8")
            lazy = True
        except OSError:
            pass
    if not lazy:
        out += [text.strip(), ""]
        return out
    suspects = [ln for ln in text.splitlines() if "SUSPECT:" in ln]
    out.append(f"Full note ({len(text)} chars): `{PLAN_NOTE_COMPANION}`, "
               "beside this file — Read it before you rewrite `_plan.md` "
               "(the rewrite contract is unchanged).")
    if suspects:
        out += ["", "`SUSPECT:` lines awaiting adjudication:"]
        out += [f"- {ln.strip()}" for ln in suspects[:12]]
    out.append("")
    return out


def _section_current_directive(conn: sqlite3.Connection,
                               problem: str) -> list[str]:
    """Surface the current `problems.strategist_directive` so Strategist
    can see what it (or a prior wake) wrote previously and maintain it
    as a rolling hint document — typically a curated list of mathlib
    lemmas / API surface relevant to the active branches, accumulated
    across routine ticks.

    EmitDirective writes overwrite this slot. Showing the current
    contents lets Strategist diff-update (keep useful entries, prune
    stale ones, add new findings) instead of either blindly appending
    or wiping prior context.

    Empty / NULL directive → returns []. Pre-Phase-2 schema (column
    missing) → returns []. Mirror of `context._section_strategist_
    directive` (which surfaces directive to *workers*); this variant
    surfaces it to Strategist itself.
    """
    try:
        row = conn.execute(
            "SELECT strategist_directive FROM problems WHERE name = ?",
            (problem,),
        ).fetchone()
    except sqlite3.OperationalError:
        return []
    if row is None:
        return []
    directive = row["strategist_directive"]
    if directive is None or not str(directive).strip():
        return []
    return [
        "## Current standing directive",
        "",
        "(Visible to every worker's Context.md until you overwrite it. "
        "Curate, don't accumulate: each update merges, shortens and "
        "retires as well as appends.)",
        "",
        str(directive).strip(),
        "",
    ]


def _section_tree_inline(conn: sqlite3.Connection,
                         workspace: Path, problem: str) -> list[str]:
    """Tree SUMMARY header for the Strategist (2026-07-13, user call):
    status counts + the non-proved exception list + a pointer to the
    on-disk TREE.md. The full tree left the per-wake context — on a
    mature problem it was ~10KB that was >90% the proved-brick roster
    (already in the catalog index), while the decision-relevant nodes
    are the handful of exceptions listed here. For structure, dead-
    branch forensics and OR-alternative history the agent reads TREE.md
    on demand (dispatcher-maintained every cascade; reading the file
    was already its habit). The frontier=True collapsed render this
    replaced is deleted from tree.py."""
    rows = conn.execute(
        "SELECT slug, status, attempts FROM goals WHERE problem = ?"
        " ORDER BY id", (problem,)).fetchall()
    if not rows:
        # Goal rows are written at COMMIT, so a brick in flight when
        # this snapshot compiles is invisible here yet answers a live
        # `decl` query minutes later — an agent read that mismatch as
        # the summary lying to it (feedback, 2026-08-25). Say what the
        # emptiness means and where the live answer is.
        return ["## TREE", "",
                "(no goals recorded when this snapshot compiled — "
                "dispatches in flight land at commit; `inspect` "
                "`decl`/`find` answer live)", ""]
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    count_line = " / ".join(
        f"{n} {s}" for s, n in sorted(counts.items(), key=lambda kv: -kv[1]))
    tree_path = db.problem_dir(workspace, problem) / "TREE.md"
    try:
        rel = tree_path.relative_to(workspace).as_posix()
    except ValueError:
        rel = "TREE.md"
    out = [
        "## TREE",
        "",
        f"**Counters:** {count_line}",
        "",
    ]
    # The alive roster left this section on 2026-08-26 (user backlog
    # item d): it was byte-for-byte isomorphic to `## Active goals`
    # right below — two copies of the same list, re-sent every loop
    # step, and the 08-24 autopsy's dominant "surfaces disagree"
    # feedback pair (~83 entries) was exactly these twins drifting
    # apart mid-wake. One roster lives in `## Active goals`; this
    # section keeps the counters and the file pointer.
    # Pointer wording 2026-08-15: the old promise ("dead-branch
    # forensics, OR-alternative history") was measured against every
    # TREE.md read on union_closed and found unused — a dead `via sNN`
    # carries no cause to read. What readers actually do there is check
    # statuses the snapshot above can't be trusted for; say that, and
    # name the sections that now answer it.
    out += [
        f"_Full tree: `{rel}` (dispatcher-rewritten every cascade). "
        f"That file is LIVE and this section is not: re-read it before "
        f"asserting any goal's status. Its by-status sections "
        f"(`## Shelved`, `## Open`, …) list every non-proved goal with "
        f"its ancestor path; `## Root` and `## Lemmas` hold the full "
        f"trees._",
        "",
    ]
    return out


def _section_charter(conn: sqlite3.Connection, workspace: Path,
                     problem: str,
                     group_id: "int | None") -> list[str]:
    """The group's OWN charter, inline, at every depth (v40) — the top
    group's is the problem's goal, a sub-group's is its Delegate brief.
    One section, one meaning; the retired `## Manifest` section's
    charter::Manifest override becomes structural.

    The top group also gets a Defs.lean preview so the Strategist can
    decide whether RequestUserAmend on Defs.lean is needed
    (statement-vocabulary missing). An ABSENT Defs.lean renders
    nothing: pure-NL problems have none by design (Phase 6), and the
    old placeholder ("does not exist — RequestUserAmend candidate") was
    a standing lure that mislabelled the legal state as a defect with a
    human-escalation hint attached (user call 2026-07-13)."""
    from ...state import groups as _groups
    row = (_groups.get(conn, int(group_id)) if group_id is not None
           else _groups.top_group(conn, problem))
    charter = str(row["charter"]).strip() if row is not None else ""
    top = _groups.is_top(row)
    out = ["## Your charter", ""]
    if charter:
        out.append(charter)
    if not top:
        out += ["", "The chain above yours, and what it already handed "
                "back: `charter.md`."]
    if top:
        defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
        if defs_path.exists():
            out += ["", "### Defs.lean", ""]
            try:
                defs_text = defs_path.read_text(encoding="utf-8")
                out.append(f"```lean\n{defs_text}\n```")
            except OSError:
                out.append("(Defs.lean unreadable)")
    out.append("")
    return out


def _section_user_word_strategist(intent: "intent_mod.ProblemIntent") -> list[str]:
    """The user's word — standing directives, verbatim, at EVERY depth
    (v40). This is the channel the retired Manifest could not keep open:
    a sub-group judged only against its charter never heard the user
    again. The word is never part of the claim under judgment — it
    governs conduct, and only the user edits it."""
    if not intent.word:
        return []
    return [
        "## The user's word",
        "",
        "Standing directives from the user, for every group at every "
        "depth. Act on them this wake where applicable; they override "
        "conflicting habits and are never yours to edit.",
        "",
        intent.word,
        "",
    ]


def _section_paper_index_strategist(intent: intent_mod.ProblemIntent,
                                    workspace: Path,
                                    conn=None,
                                    attempts_dir: "Path | None" = None,
                                    ) -> list[str]:
    """Strategist view of the paper section: the shared navigation
    block + the provenance-recording instruction + the FetchPaper
    channel (conditional — only a paper-bound problem renders them;
    prompt stays static per the prompt-editing principle)."""
    lines = context._section_paper_index(intent, workspace, conn,
                                         attempts_dir=attempts_dir)
    if not lines:
        return lines
    return lines + [
        "Every `MarkDeliverable` on this problem MUST include "
        "`paper_ref: \"p.N <label>\"` in its payload (where the paper "
        "states the claim) — it is shown to the human at sign-off.",
        "When the paper cites a work you genuinely need (a proof "
        "detail this paper omits), fetch it yourself during this "
        "wake: `paper_search(query=\"<citation as printed>\")` (or "
        "`doi=...`) resolves open copies, then "
        "`paper_fetch(target=<url|arxiv id>, problem=<this problem>, "
        "reason=<why>)` shelves and binds it; fetched papers appear "
        "under `### Auxiliary papers` on later wakes.",
        "",
    ]


def compile_strategist_context(conn: sqlite3.Connection, *,
                               problem: str, trigger_kind: str,
                               attempts_dir: Path,
                               workspace: Path,
                               intent: intent_mod.ProblemIntent,
                               pending_review_id: int | None = None,
                               group_id: "int | None" = None,
                               ) -> Path:
    """Write Context.md for the Strategist agent into attempts_dir.

    Sections (in order, all optional if their source is empty):
      - Trigger (always; includes pending review target for T2)
      - Active goals
      - Recent decisions (failure_replay)
      - TREE
      - Charter (own group, inline) + user word
    """
    section_names = ["trigger", "user_word"]
    sections: list[list[str]] = [
        _section_trigger(trigger_kind, pending_review_id, conn,
                 workspace),
        _section_user_word_strategist(intent),
    ]
    from ...pipeline.strategist import audit as _audit
    if trigger_kind == "routine_fired" and group_id is not None:
        # The action wake a fired audit seated: its findings lead the
        # Context, verbatim (2026-08-30).
        pending = _audit.pending_fired_verdict(conn, int(group_id))
        if pending is not None:
            section_names.append("routine_verdict")
            sections.append(_audit.render_verdict_section(pending, conn))
    # T2 review_context (Phase 2 §2.2) — failure brief + existing
    # strategies + ancestor chain. Un-gated from the pending_review
    # trigger (owner design 2026-08-26, wake merge): the
    # review-discharge rule already FORCES every non-routine wake to
    # rule on pending-review goals, and a batch_done wake was ruling
    # blind — obligated without the dossier. Every non-routine wake now
    # carries the dossier for every waiting goal, full for the first
    # few, one line + the lazy companions beyond (context diet).
    review_ids: "list[int]" = []
    if trigger_kind != "routine":
        review_ids = [int(r["id"]) for r in conn.execute(
            "SELECT id FROM goals WHERE problem = ?"
            "  AND status = 'pending_strategist_review' ORDER BY id",
            (problem,))]
    if pending_review_id is not None:
        # The wake's own target leads, whatever the ordering says.
        review_ids = ([pending_review_id]
                      + [i for i in review_ids if i != pending_review_id])
    for rid in review_ids[:_REVIEW_DOSSIER_CAP]:
        section_names += [f"review_failure_g{rid}",
                          f"review_adjudications_g{rid}",
                          f"review_strategies_g{rid}",
                          f"review_ancestors_g{rid}"]
        sections += [
            _section_pending_review_failure(conn, rid, attempts_dir),
            _section_pending_review_adjudications(
                conn, rid, attempts_dir),
            _section_pending_review_strategies(conn, rid),
            _section_pending_review_ancestors(conn, rid),
        ]
    if len(review_ids) > _REVIEW_DOSSIER_CAP:
        rest = review_ids[_REVIEW_DOSSIER_CAP:]
        section_names.append("review_overflow")
        sections.append(
            ["## More goals awaiting your review", ""]
            + [f"- g{rid} — dossier not inlined; adjudication history "
               f"in ADJUDICATIONS.md, statement via inspect decl"
               for rid in rest]
            + ["", "Every goal above ALSO waits on your verdict in "
               "this same wake.", ""])
    # Phase 2.5 — surface unack Inject batches on every trigger when
    # any exist (not gated on trigger_kind='inject_batch_done'). See
    # `_section_inject_batch_outcomes` docstring for the race rationale.
    # `_section_pending_reopens` runs on every trigger too — Strategist
    # may discover a Reopen candidate while waking on pending_review /
    # routine / inject_batch_done alike. Empirically (brouwer 2026-05-22)
    # the loop "ConfirmShelve promises retry → Forward lands → Strategist
    # never Reopens" was never closed by the agent on its own; surfacing
    # the cross-reference gives it a structured cue.
    section_names += ["stall_warning", "ingest_gate", "disproof_guidance",
                      "your_group", "groups_in_flight", "programme",
                      "directive",
                      "plan_note", "inject_batches", "pending_reopens",
                      "active_goals", "failure_replay", "tree", "catalog",
                      "charter", "paper_index"]
    sections += [
        _section_stall_warning(conn, problem, group_id),
        _section_ingest_gate(conn, problem, group_id, intent=intent),
        _section_disproof_guidance(conn, problem),
        _section_your_group(conn, problem, group_id),
        _section_groups_in_flight(conn, problem, group_id),
        _section_programme_strategist(conn, problem, group_id,
                                      attempts_dir=attempts_dir),
        _section_current_directive(conn, problem),
        _section_plan_note(conn, workspace, problem, group_id,
                           attempts_dir=attempts_dir),
        _section_inject_batch_outcomes(conn, problem,
                                       workspace=workspace,
                                       group_id=group_id,
                                       attempts_dir=attempts_dir),
        _section_pending_reopens(conn, problem, trigger_kind),
        _section_active_goals(conn, workspace, problem),
        _section_failure_replay(conn, problem),
        _section_tree_inline(conn, workspace, problem),
        _section_catalog_index_strategist(conn, problem, attempts_dir),
        _section_adjudications_pointer(conn, problem, attempts_dir),
        _section_charter(conn, workspace, problem, group_id),
        _section_paper_index_strategist(intent, workspace, conn,
                                        attempts_dir=attempts_dir),
    ]
    # The lines this group has in flight — what the routine audit rules
    # on per line (criteria 3, 4). Rendered for every wake; the ROUTINE
    # wake also freezes the roster as `_audit_roots.json`, the snapshot
    # its verdict is checked against (a line that grows while the
    # auditor thinks is not its omission).
    lines = _audit.in_flight_lines(conn, problem, group_id)
    section_names.append("lines_in_flight")
    sections.append(_audit.render_lines_section(lines))
    if trigger_kind == "routine":
        _audit.write_roots_snapshot(attempts_dir, lines)
        # Curation surface for the kb_curation.json sidecar — only the
        # routine wake gets it (the power is structurally routine-only;
        # moved from the retired audit wake 2026-07-25).
        section_names.append("kb_lessons")
        sections.append(
            _section_kb_lessons_curation(conn, problem, attempts_dir))
    parts: list[str] = [f"# Strategist context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    # v35 — the `## Your group` section points a sub-group at
    # `charter.md`; the file has to be there. It existed only inside the
    # JUDGE's projection, so the judge reviewed against the charter while
    # the author worked from the whole problem's goal — two sides of
    # one review reading different tasks.
    _write_charter_file(conn, problem, attempts_dir, group_id)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    context.write_context_stats(
        attempts_dir, label=f"strategist {problem}",
        names=section_names, sections=sections)
    return out


def _write_charter_file(conn: sqlite3.Connection, problem: str,
                        attempts_dir: Path,
                        group_id: "int | None") -> None:
    """Stage `charter.md` beside Context.md for a sub-group — the same
    bytes the judge gets, from the same renderer. Author and judge must
    be reading one task."""
    from ...state import groups as _groups
    text = _groups.charter_digest(conn, problem, group_id)
    if text:
        (attempts_dir / "charter.md").write_text(text, encoding="utf-8")


def _section_groups_in_flight(conn: sqlite3.Connection, problem: str,
                              group_id: "int | None") -> list[str]:
    """Conditional (v35): renders only when this group has live children.

    Two jobs in one section. It is the parent's ONLY view of what it
    delegated and is still waiting on — the batch-outcome scoreboard
    lists finished work, so without this a parent knows a batch is open
    but not which charters are out. And it carries `CloseGroup`, whose
    usability depends on both halves: the verb is unusable without a
    group id to name, and showing the verb to a group that has no
    children is the same false affordance the `ReturnToParent` section
    avoids. With no children the whole section disappears.
    """
    if group_id is None:
        return []
    from ...state import groups as _groups
    kids = _groups.children(conn, int(group_id), active_only=True)
    if not kids:
        return []
    out = ["## Your groups in flight", ""]
    for k in kids:
        charter = " ".join(str(k["charter"] or "").split())
        if len(charter) > 200:
            charter = charter[:200].rstrip() + "…"
        age = _age_hint(str(k["created_at"] or ""))
        out.append(f"- group {k['id']} — {charter}"
                   + (f" (open {age})" if age else ""))
    out += [
        "",
        "- `CloseGroup` — `target_group_id`, `reason`. Retire one when "
        "your route no longer needs its charter; its own sub-projects "
        "close with it. Difficulty is not a reason — whether to give up "
        "is that group's call.",
        "",
    ]
    return out


def _age_hint(created_at: str) -> str:
    """`2h14m` since an ISO stamp; empty when it cannot be parsed."""
    from datetime import datetime, timezone
    try:
        started = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return ""
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    secs = (datetime.now(timezone.utc) - started).total_seconds()
    if secs < 60:
        return "just now"
    mins = int(secs // 60)
    return f"{mins // 60}h{mins % 60:02d}m" if mins >= 60 else f"{mins}m"


def _section_your_group(conn: sqlite3.Connection, problem: str,
                        group_id: "int | None") -> list[str]:
    """Conditional (v35): renders ONLY for a sub-group.

    The static prompt is written for the group that faces the human, and
    two of its statements are wrong one level down — `Ingest` is not the
    problem's exit, and `RequestUserAmend` is not this group's channel.
    Rather than scrub those from three prompts (they are correct for the
    reader they were written for), the Context overrides them here: an
    agent trusts the Context copy, so a dynamic section that enumerates
    actions must agree with the static prompt or replace it explicitly.

    Empty for the top group — the static prompt already says everything
    true for it, so today's single-group runs pay nothing.
    """
    from ...state import groups as _groups
    if group_id is None:
        return []
    me = _groups.get(conn, int(group_id))
    if me is None or _groups.is_top(me):
        return []
    # Conditional affordance (owner ruling 2026-08-19): the Delegate
    # verb disappears from this group's instructions the moment it is
    # structurally unavailable — an agent told about a verb a gate will
    # refuse invents workarounds; one never told plans with AHEAD from
    # the start.
    at_cap = _groups.depth(conn, int(group_id)) >= _groups.GROUP_DEPTH_CAP
    # Guidance hand-off (2026-08-19): the parent's optional `brief`
    # rides the Delegate audit row; read back through `opened_by`.
    # Context, never part of the charter under judgment.
    guidance = ""
    if me["opened_by"] is not None:
        try:
            row = conn.execute(
                "SELECT payload FROM strategist_decisions WHERE id = ?",
                (int(me["opened_by"]),)).fetchone()
            if row is not None:
                guidance = str(json.loads(
                    row["payload"] or "{}").get("brief") or "").strip()
        except (ValueError, TypeError):
            guidance = ""
    return [
        "## Your group", "",
        "Your charter and the chain above it: `charter.md`.", "",
        *([f"Guidance from your parent (context, not the claim):\n"
           f"{guidance}", ""] if guidance else []),
        # (v40 — the old charter::Manifest override bullet is gone: the
        # prompts now say "charter" natively at every depth, so there is
        # nothing to override. Only the level-dependent verb semantics
        # remain.)
        *(["- `Delegate` is not available at your depth (the group tree "
           "caps two levels below the top). Plan follow-up work in your "
           "Roadmap's AHEAD — the next wake fires when this batch "
           "completes — or `ReturnToParent(amend)` if your charter "
           "itself needs recutting."] if at_cap else []),
        "- `Ingest` here delivers your bricks upward and ends this "
        "group, not the problem.",
        "- `ReturnToParent` — `flavour ∈ "
        "{\"refuted\",\"amend\",\"exhausted\"}`, `reason` (what was "
        "tried, where it died, what was learned). `refuted` also takes "
        "`target_goal_id`: the `<slug>_disproof` brick the gate minted "
        "for a node in your chain. "
        "`amend` also takes `proposed_charter`: the claim you believe "
        "is provable.",
        "- `RequestUserAmend` is not yours → "
        "`ReturnToParent(amend)`, naming the file and what is wrong.",
        "",
    ]


REJECTED_COMPANION = "REJECTED.md"


def _section_programme_strategist(conn: sqlite3.Connection,
                                  problem: str,
                                  group_id: "int | None" = None,
                                  attempts_dir: "Path | None" = None,
                                  ) -> list[str]:
    """Research mode (research_mode_design.md §2): the current
    Programme rev inline — it is the commitment object your proposal
    revises (route/planning lives HERE, not in the plan note) — plus
    the Adversary's reservations on it, and, after a discarded cycle,
    the one-line rejection record (never the failed draft) followed by
    the judge's LAST rebuttal inline and every round's rebuttal in the
    `REJECTED.md` companion (owner ruling 2026-08-30: group 504's
    successor saw one line plus its own plan note — its belief, not the
    refutation — and re-argued the refuted route for five more rounds).
    The draft stays withheld: the rebuttal is the judge's text and
    invites no re-skin; the draft is the author's and does."""
    import json as _json
    from ...state import programme as _programme
    try:
        row = _programme.current_rev(conn, problem, group_id)
        notice = _programme.rejection_notice(conn, problem, group_id)
    except sqlite3.OperationalError:
        return []
    out: list[str] = []
    # Judge dialogue is rendered in its OWN top-level section, after the
    # rev text and never inside it (2026-08-02 judge feedback): appended
    # bare under `## Programme` it read as Programme prose, so the file on
    # disk ended at the risk register while this view carried three more
    # lines — and the same judge is told to penalise dialogue residue in
    # the Programme. The framework must not author what it prosecutes.
    reservations: list[str] = []
    if row is None:
        out += ["## Programme", "",
                "(none yet — the proposal you deliver this wake founds "
                "rev 1)", ""]
    else:
        out += [f"## Programme (rev {row['rev']}, passed "
                f"{str(row['created_at'])[:10]})", "",
                str(row["body"]).strip(), ""]
        try:
            verdict = _json.loads(row["verdict"] or "{}")
        except ValueError:
            verdict = {}
        reservations = [str(r) for r in (verdict.get("reservations") or [])]
    if notice:
        out += ["### Previous proposal rejected", "", notice, ""]
        # An infra discard already hands the draft and its transcript
        # over inside the notice; the adversarial one gets the rebuttal.
        if "### Uncommitted draft" not in notice:
            out += _rebuttal_surface(conn, problem, group_id, attempts_dir)
    if reservations:
        out += [f"## Adversary reservations on rev {row['rev']}", "",
                "Advisory notes from the judge that passed it — not part"
                " of the Programme text above.", ""]
        out += [f"- {r}" for r in reservations]
        out.append("")
    return out


def _rebuttal_surface(conn: sqlite3.Connection, problem: str,
                      group_id: "int | None",
                      attempts_dir: "Path | None") -> list[str]:
    """Inline: the round that killed the latest discarded rev. Lazy:
    every round of the whole discarded cycle, written as the
    `REJECTED.md` companion beside Context.md. Never a draft."""
    from ...state import programme as _programme
    cycle = _programme.rejection_cycle(conn, problem, group_id)
    if not cycle:
        return []
    out: list[str] = []
    last = cycle[-1]
    rnd, crits = _programme.last_rebuttal(last)
    if crits:
        out += [f"**Why it died — the judge's last rebuttal (round {rnd} "
                f"of rev {last['rev']}):**", ""]
        out += [f"- {c}" for c in crits]
        out.append("")
    if attempts_dir is not None:
        md = _programme.rejection_history_md(cycle)
        if md:
            (attempts_dir / REJECTED_COMPANION).write_text(
                md, encoding="utf-8")
            span = (f"rev {cycle[0]['rev']}" if len(cycle) == 1
                    else f"revs {cycle[0]['rev']}–{last['rev']}")
            out += [f"Every round's rebuttal of this discarded cycle "
                    f"({span}; no drafts): `{REJECTED_COMPANION}` beside "
                    f"this file. Read it before you argue a route those "
                    f"rounds already refuted.", ""]
    return out


def _section_catalog_index_strategist(conn: sqlite3.Connection,
                                      problem: str,
                                      attempts_dir: Path) -> list[str]:
    """Strategist's citable-catalog surface (2026-07-13, user call):
    slug index inline + exact statements in the `CATALOG.md` companion.
    This is the machine-generated replacement for the hand-maintained
    LANDED-CATALOG block the Strategist grew inside the standing
    directive (drift-prone: pipeline renames burned the hand-copy four
    times) — copy signatures from the companion into briefs instead of
    hand-maintaining them."""
    rows = context.write_catalog_companion(conn, problem, attempts_dir)
    if not rows:
        return []
    # Recent tail only (2026-07-14, user call): the full slug list grew
    # linearly with proved count (438 bricks = 16KB, 47% of the
    # context) while its lookup roles are covered elsewhere — dedupe
    # gate catches re-inventions, grep serves name checks. What stays
    # inline is the freshness floor: the newest bricks, rendered from
    # goal records, as ground truth against a stale plan note.
    recent = rows[-_CATALOG_RECENT_N:]
    out = [
        "## Proved catalog (index)",
        f"_{len(rows)} landed bricks — full list & exact statements in"
        f" `{context.catalog_companion_path(attempts_dir)}`"
        " (read-only, NOT in your cwd; machine-generated from what actually landed"
        " — never drifts from pipeline renames; written when this wake"
        " started, so a brick that lands mid-wake reaches `TREE.md`"
        " before it reaches here; grep it by slug; every"
        " worker gets its own copy beside its Context.md, so cite it by"
        " bare name in briefs). Copy signatures from there into"
        " briefs/directives instead of hand-maintaining a catalog."
        f" The {len(recent)} newest:_",
        "",
    ]
    out += [f"- `{r['slug']}`" for r in recent]
    out.append("")
    return out


def _section_adjudications_pointer(conn: sqlite3.Connection, problem: str,
                                   attempts_dir: Path) -> list[str]:
    """Two-line pointer to the machine-generated ruling history (the
    lazily loaded layer; owner call 2026-08-25 — nothing inlined here
    beyond the pointer). Written fresh each wake so it never drifts."""
    from .. import context
    n = context.write_adjudications_companion(conn, problem, attempts_dir)
    if not n:
        return []
    return [
        "## Adjudication history (park rulings)",
        f"_{n} goal(s) carry ConfirmShelve rulings — full text in"
        f" `{context.adjudications_companion_path(attempts_dir)}`"
        " (read-only, NOT in your cwd; grep by `g<id>` or slug)."
        " Before parking or reviving a goal, read its section:"
        " a recurring park is a recorded decision, and overturning it"
        " should answer the recorded reason._",
        "",
    ]


def _section_kb_lessons_curation(conn: sqlite3.Connection, problem: str,
                                 attempts_dir: Path) -> list[str]:
    """Routine-wake curation surface (2026-07-13; audit wake retired
    into routine 2026-07-25): the problem's GLOBAL lesson index — the
    same `[id-N] title` cue lines every worker sees — with full bodies
    in the `LESSONS.md` companion so the wake can adjudicate broken /
    superseded / duplicate entries and emit `kb_curation.json`.
    Lessons only: antipatterns are node-scoped and mechanically
    captured, outside the curation mandate."""
    from ...state import kb
    rows = kb.global_lessons(conn, problem)
    if not rows:
        return []
    out = [
        "## Lesson KB (curation surface)",
        "_Every worker sees these titles on every spawn; bodies are in"
        " the `LESSONS.md` companion. This index is curatable on this"
        " wake via `kb_curation.json`._",
        "",
    ]
    body_lines = [f"# Lessons — full recipes ({problem})", ""]
    for r in rows:
        title = (r["title"] or "").strip()
        out.append(f"- [id-{r['id']}] {title}")
        body_lines += [f"## [id-{r['id']}] {title}", ""]
        body = (r["body"] or "").strip()
        if body:
            body_lines += [body, ""]
    out.append("")
    try:
        (attempts_dir / "LESSONS.md").write_text(
            "\n".join(body_lines) + "\n", encoding="utf-8")
    except OSError:
        pass  # index alone still lets title-level curation proceed
    return out


