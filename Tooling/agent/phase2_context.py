"""Phase 2 — Strategist + Forward Context.md compilation.

Strategist + Forward operate at problem-level, not goal-level — so
they bypass `compile_context` (which is hard-wired to a specific goal
row) and assemble Context.md from problem-level facts only.

Strategist sees:
  - `trigger_kind`
  - Active goal list with statements + status
  - Recent strategist_decisions + their outcomes (self-feedback)
  - Proof tree, FRONTIER view (settled subtrees collapsed; #2)
  - Manifest + Defs.lean (for T0 / T3)
  - Pending review target (for T2)

Forward sees:
  - Strategist brief (from queue.decision_id FK)
  - Library state (cross-problem proved lemmas)
  - TREE.md inline
  - Past Forward output history
  - Mathlib hints from Manifest (loogle is agent-driven via Bash tool)
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..state import db, manifest, tree
from . import context


# ---------------------------------------------------------------------
# Strategist
# ---------------------------------------------------------------------

def _section_trigger(trigger_kind: str, pending_review_id: int | None,
                     conn: sqlite3.Connection) -> list[str]:
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
                f"- statement: `{g['statement']}`",
                f"- depth: {g['depth']}",
                f"- attempts: {g['attempts']}",
                "",
            ]
    return lines


def _section_ingest_gate(conn: sqlite3.Connection,
                         problem: str) -> list[str]:
    """Phase 6 — context-conditional Ingest availability note (design ④):

      - root exists, NOT proved → surface "Ingest is unavailable" (the
        HARD gate would reject it), so the Strategist doesn't burn a
        decision on it.
      - root still `frozen` (never injected) → additionally steer the
        opening moves: Forward prerequisite lemmas first; don't Inject
        Backward on the root in the same batch as its prerequisites.
      - root proved, or no root (pure-NL) → say nothing; the prompt's
        standing instruction ("commit Ingest once the Manifest's
        requirements are met") is the only voice — these notes would be
        pure noise once they stop being true.
    """
    root = conn.execute(
        "SELECT status FROM goals WHERE problem = ? AND origin = 'root'"
        " LIMIT 1", (problem,)).fetchone()
    if root is None or str(root["status"]) == "proved":
        return []
    lines = [
        "## Ingest availability",
        "",
        f"`Ingest` is unavailable — the root goal is not yet proved "
        f"(status: `{root['status']}`; hard exit gate).",
        "",
    ]
    if str(root["status"]) == "frozen":
        lines += [
            "Forward the root's prerequisites first; don't "
            "`Inject(Backward)` on the root in the same batch.",
            "",
        ]
    return lines


def _section_stall_warning(conn: sqlite3.Connection,
                           problem: str) -> list[str]:
    """Structural stall detection (B-2 fix).

    Surfaces a header when:
      - `Ingest` not yet committed AND
      - zero open goals reachable AND
      - no in-flight Backward/Builder/Forward worker.

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
    if not db.is_problem_stalled(conn, problem):
        return []
    return [
        "## Framework stalled",
        "",
        "Structural deadlock detected: this problem has not been"
        " `Ingest`ed, no `open` goal is reachable for BFS dispatch, and"
        " no Backward/Builder/Forward worker is in flight. The framework"
        " cannot dispatch any worker on this problem until you intervene.",
        "",
        "Typical causes:",
        "",
        "- The problem is FRESH — nothing has been injected yet; your"
        " job is to commit the first Inject batch from the Manifest.",
        "- Everything you planned is proved and the Manifest's"
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
        " Choose one of: `Inject(Backward|Builder, target_goal_id=...)`"
        " (revive a `shelved` / `pending_strategist_review` goal with"
        " an explicit pipeline + brief), `Inject(Forward)` (build the"
        " missing prerequisite), `Ingest` (every Manifest requirement is"
        " satisfied — the terminal judgment), `ConfirmShelve` (truly"
        " cannot proceed — followed by an Inject that pivots), or"
        " `RequestUserAmend` (Manifest scope decision needed).",
        "",
    ]


def _section_pending_review_failure(
    conn: sqlite3.Connection, pending_review_id: int,
) -> list[str]:
    """Dead-attempt brief that triggered the review.

    Phase 2 §2.2 review_context spec calls for the failure reason
    summary. The agent's shelve description lives in
    `dead_attempts.proposal_md` (Backward / Builder write the decline
    body there before the cascade enqueues Strategist review). Without
    this section, Strategist sees only the goal statement and has no
    visibility into what the pipeline agent already articulated as
    blockers — exactly the gap that caused the take-5 SG misfire where
    Backward enumerated 5 missing Forward lemmas in `proposal_md` but
    Strategist Reopen'd with a redundant Kelly directive.
    """
    rows = list(conn.execute(
        "SELECT pipeline_id, failure_reason, failure_detail, proposal_md, ts"
        " FROM dead_attempts WHERE target_kind = 'Goal' AND target_id = ?"
        " ORDER BY id DESC LIMIT 3",
        (str(pending_review_id),),
    ))
    if not rows:
        return []
    out = ["### Recent failed attempts on this goal (newest first)", ""]
    for r in rows:
        out.append(
            f"- pipeline=`{str(r['pipeline_id'])[:8]}`  "
            f"reason=`{r['failure_reason']}`  ts={r['ts']}"
        )
        detail = (r["failure_detail"] or "").strip()
        if detail:
            if len(detail) > 400:
                detail = detail[:400].rstrip() + "…"
            out.append(f"  detail: {detail}")
        proposal = (r["proposal_md"] or "").strip()
        if proposal:
            # 1500→4000 (2026-07-05): the shelve brief IS the review's
            # primary evidence, and 1500 chars truncated real proposals
            # mid-signature at the exact payload the verdict hinges on
            # (feedback: Strategist reconstructed it by source-grepping).
            if len(proposal) > 4000:
                proposal = proposal[:4000].rstrip() + "\n…(truncated)"
            out += ["", "  agent brief:", "  ```", proposal, "  ```"]
        out.append("")
    return out


def _section_pending_review_strategies(
    conn: sqlite3.Connection, pending_review_id: int,
) -> list[str]:
    """Existing strategies on the pending-review goal.

    Phase 2 §2.2 review_context spec: '既有 strategy 內容'. Surfaces
    what's already been tried structurally so Strategist can judge
    'Reopen with directive' vs 'Inject Forward to expand toolkit' from
    the actual proposal text — not from the goal statement alone.
    """
    rows = list(conn.execute(
        "SELECT id, status, proposal_md, created_at"
        " FROM strategies WHERE goal_id = ?"
        " ORDER BY id",
        (pending_review_id,),
    ))
    if not rows:
        return []
    out = ["### Existing strategies on this goal", ""]
    for r in rows:
        out.append(
            f"- s{r['id']} status=`{r['status']}` created={r['created_at']}"
        )
        prop = (r["proposal_md"] or "").strip()
        if prop:
            if len(prop) > 800:
                prop = prop[:800].rstrip() + "\n…(truncated)"
            out += ["", "  proposal:", "  ```", prop, "  ```"]
        out.append("")
    return out


def _section_pending_review_ancestors(
    conn: sqlite3.Connection, pending_review_id: int,
) -> list[str]:
    """Walk goal → parent-strategy → strategy.goal_id chain upward to
    root. Phase 2 §2.2 review_context spec: 'ancestor 鏈'.

    At most one live parent strategy per goal (BFS invariant — others
    are superseded or dead). Walk picks the live one if any, else the
    most recently linked dead strategy (so context shows the historical
    chain even after upstream death).
    """
    chain: list[sqlite3.Row] = []
    seen: set[int] = set()
    cur = pending_review_id
    while cur not in seen:
        seen.add(cur)
        # Find parent strategy via strategy_subgoals
        parent = conn.execute(
            "SELECT s.id AS sid, s.goal_id AS pg, s.status AS sstatus"
            " FROM strategy_subgoals ss"
            " JOIN strategies s ON s.id = ss.strategy_id"
            " WHERE ss.subgoal_id = ?"
            " ORDER BY CASE s.status WHEN 'proposed' THEN 0"
            "                       WHEN 'succeeded' THEN 1"
            "                       ELSE 2 END, s.id DESC"
            " LIMIT 1",
            (cur,),
        ).fetchone()
        if parent is None:
            break
        pg = int(parent["pg"])
        g = db.get_goal(conn, pg)
        if g is None:
            break
        chain.append(g)
        cur = pg
    if not chain:
        return ["### Ancestor chain", "",
                "(none — this goal is its own root)", ""]
    out = ["### Ancestor chain (parent → root)", ""]
    for g in chain:
        st = str(g["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        marker = " (ROOT)" if g["origin"] == "root" else ""
        out.append(
            f"- [{g['id']}] depth={g['depth']} status=`{g['status']}`"
            f" `{g['slug']}`{marker}"
        )
        out.append(f"  `{st}`")
    out.append("")
    return out


def _section_inject_batch_outcomes(conn: sqlite3.Connection,
                                   problem: str) -> list[str]:
    """Surface every Inject batch on this problem that completed since
    the last Strategist commit (`last_strategist_at` ratchet — see
    `db.unacknowledged_inject_batches`).

    Emitted on ANY trigger when unack batches exist, not gated on
    `trigger_kind='inject_batch_done'`. Rationale: `_maybe_enqueue_
    inject_batch_done` does not advance `last_strategist_at`; a
    concurrent Strategist invocation under a different trigger (e.g.
    pending_review) can commit between batch completion and the queued
    inject_batch_done Strategist popping — that commit advances the
    ratchet and the queued inject_batch_done call no longer recognises
    the batch as unack. By always surfacing here, whichever Strategist
    runs first sees the batch and gets a chance to act on it. Acking
    via the ratchet still prevents double-processing across calls.

    Per-step "landed" line: `produced_goal_id` (backfilled by the
    Forward commit / redispatch target) resolves each step to the decl
    that actually exists — kernel truth, not the Strategist's past
    intent. The Strategist repeatedly reported having to guess which
    decl a `success` step landed as (feedback 2026-07-04, 30+ entries);
    an earlier docstring claimed attribution was impossible, which
    predates the `produced_goal_id` column.
    """
    batch_ids = db.unacknowledged_inject_batches(conn, problem)
    if not batch_ids:
        return []
    out = ["## Completed Inject batches (newest first)", ""]
    placeholders = ",".join("?" * len(batch_ids))
    rows = list(conn.execute(
        f"SELECT d.id, d.batch_id, d.brief, d.payload, d.outcome,"
        f" d.outcome_detail, d.updated_at,"
        f" g.slug AS landed_slug, g.status AS landed_status,"
        f" g.statement AS landed_statement"
        f" FROM strategist_decisions d"
        f" LEFT JOIN goals g ON g.id = d.produced_goal_id"
        f" WHERE d.batch_id IN ({placeholders})"
        f" ORDER BY MAX(d.updated_at) OVER (PARTITION BY d.batch_id) DESC,"
        f"          d.batch_id, d.id",
        batch_ids,
    ))
    grouped: dict[str, list[sqlite3.Row]] = {}
    order: list[str] = []
    for r in rows:
        bid = str(r["batch_id"])
        if bid not in grouped:
            grouped[bid] = []
            order.append(bid)
        grouped[bid].append(r)

    def _step_idx(r: sqlite3.Row) -> int:
        try:
            return int(json.loads(str(r["payload"]) or "{}")
                       .get("step_index", 0))
        except (ValueError, TypeError):
            return 0

    for bid in order:
        steps = grouped[bid]
        steps.sort(key=_step_idx)
        out.append(f"### Batch `{bid[:8]}` ({len(steps)} steps)")
        out.append("")
        for r in steps:
            idx = _step_idx(r)
            # This is the batch the wake is ABOUT — show its feedback in
            # full (generous cap, not the short recap truncation used by
            # `_section_failure_replay`) so the Strategist can compare what
            # it briefed against what actually came back (#4).
            brief = (r["brief"] or "").strip()
            if len(brief) > 1200:
                brief = brief[:1200].rstrip() + "…"
            outcome_text = r["outcome"] or "(no outcome)"
            out.append(f"- **step {idx}** outcome=`{outcome_text}`")
            if r["landed_slug"]:
                stmt = " ".join(str(r["landed_statement"] or "").split())
                if len(stmt) > 300:
                    stmt = stmt[:300].rstrip() + "…"
                out.append(
                    f"  landed: `{r['landed_slug']}` "
                    f"(status={r['landed_status']})"
                    + (f" — `{stmt}`" if stmt else ""))
            out.append(f"  brief: {brief}")
            detail = (r["outcome_detail"] or "").strip()
            if detail:
                if len(detail) > 1200:
                    detail = detail[:1200].rstrip() + "…"
                out.append(f"  why: {detail}")
        out.append("")
    return out


def _section_pending_reopens(conn: sqlite3.Connection,
                             problem: str,
                             trigger_kind: str) -> list[str]:
    """Surface shelved goals whose promised follow-up batch just landed.

    Promise model: when Strategist ships a decision array `[ConfirmShelve(G),
    Inject(F1), Inject(F2), ...]` it's implicitly saying "I'm shelving G
    because I'm injecting F1/F2 to unblock it; wake me to re-evaluate G
    when they're done". `_commit_one` writes the shared `batch_id` on
    every row in the array, so the framework can later recover the
    promise by querying ConfirmShelve rows whose batch siblings (Inject
    rows) have all reached terminal `outcome`.

    Gated on `trigger_kind == 'inject_batch_done'` — that's the wake
    fired when a batch's last Inject reaches terminal. Other triggers
    (routine / pending_review / first_launch) skip this section.

    Scoping rule (brouwer 2026-05-22 G2): pre-fix this section dumped
    *every* shelved goal in the problem on every inject_batch_done
    wake, causing Strategist to re-ConfirmShelve g2771 four times with
    no new evidence between calls. Post-fix it lists ONLY goals whose
    own promised batch (the one cited by their latest ConfirmShelve)
    is now complete — i.e., goals where the Inject(s) Strategist
    explicitly designed to address them have produced their outcomes
    and there's now genuine new evidence to re-evaluate.

    Fortuitous unblock (a Forward designed for an unrelated batch
    happens to make a shelved goal provable) is handled separately by
    the G1 dedupe revival pass (`find_shelved_revivals_for_forward` →
    `_revive_shelved_alias`) — no need to re-surface unrelated
    shelved goals here.

    Per surfaced goal:
      * latest ConfirmShelve `reason` (the explicit promise);
      * the now-complete promised batch's Inject decisions + their
        produced goals (so Strategist sees exactly what landed).
    """
    if trigger_kind != "inject_batch_done":
        return []

    # Find shelved goals whose latest ConfirmShelve was committed in a
    # batch whose every sibling Inject row has `outcome IS NOT NULL`
    # (batch fully terminal). Latest-per-goal so a goal that's been
    # re-ConfirmShelved across multiple batches surfaces against its
    # most recent promise — older batches' completion is moot.
    rows = list(conn.execute(
        """
        WITH latest_cs AS (
            SELECT g.id AS goal_id, g.slug AS goal_slug,
                   g.updated_at AS shelved_at,
                   MAX(d.id) AS cs_decision_id
            FROM goals g
            JOIN strategist_decisions d
              ON d.target_id = CAST(g.id AS TEXT)
             AND d.decision_kind = 'ConfirmShelve'
             AND d.problem = g.problem
             AND d.batch_id IS NOT NULL
            WHERE g.problem = ? AND g.status = 'shelved'
            GROUP BY g.id
        )
        SELECT lcs.goal_id, lcs.goal_slug, lcs.shelved_at,
               cs.id AS cs_id, cs.reason AS cs_reason,
               cs.batch_id AS cs_batch_id
        FROM latest_cs lcs
        JOIN strategist_decisions cs ON cs.id = lcs.cs_decision_id
        WHERE cs.batch_id NOT IN (
            -- exclude batches still in-flight: any Inject sibling
            -- with outcome NULL means the promise hasn't landed yet
            SELECT batch_id FROM strategist_decisions
            WHERE problem = ?
              AND decision_kind = 'Inject'
              AND batch_id IS NOT NULL
              AND outcome IS NULL
        )
        AND EXISTS (
            -- and the batch must contain at least one Inject — pure
            -- ConfirmShelve+Reopen batches carry no promise to wait on
            SELECT 1 FROM strategist_decisions sib
            WHERE sib.batch_id = cs.batch_id
              AND sib.decision_kind = 'Inject'
        )
        AND NOT EXISTS (
            -- and Strategist hasn't already addressed this completed
            -- batch with a newer ConfirmShelve / Reopen on the same
            -- goal (i.e., this surfacing has actually new
            -- information vs the last time we surfaced)
            SELECT 1 FROM strategist_decisions later
            WHERE later.problem = ?
              AND later.target_id = CAST(lcs.goal_id AS TEXT)
              AND later.decision_kind IN ('ConfirmShelve', 'Reopen')
              AND later.id > cs.id
        )
        ORDER BY lcs.shelved_at DESC
        LIMIT 12
        """,
        (problem, problem, problem),
    ))
    if not rows:
        return []

    out = [
        "## Pending reopen-promises",
        "",
        "Shelved goal(s) whose ConfirmShelve batch promised a follow-up "
        "Inject set — and that follow-up set has now fully landed. "
        "Strategist's own batch-time promise is the trigger; this is "
        "the moment to evaluate `Inject(Backward|Builder, target_goal_id"
        "=<id>, brief=...)` vs a further `Inject` vs a second "
        "`ConfirmShelve` with a refined promise. Fortuitous unblock by "
        "unrelated Forwards is handled "
        "automatically by the G1 dedupe revival pass — no need to "
        "re-surface unrelated shelved goals here.",
        "",
    ]
    for r in rows:
        gid = int(r["goal_id"])
        slug = str(r["goal_slug"])
        shelved_at = str(r["shelved_at"])[:19]
        reason = str(r["cs_reason"] or "").strip()
        if len(reason) > 240:
            reason = reason[:240].rstrip() + "…"
        batch_id = str(r["cs_batch_id"])

        out.append(f"### `{slug}` (id={gid}, shelved {shelved_at})")
        out.append(f"shelve reason: {reason}" if reason
                   else "shelve reason: (empty)")
        # Pull what the promised batch actually produced.
        siblings = list(conn.execute(
            "SELECT d.id, d.brief, d.target_id, d.produced_goal_id,"
            " d.outcome, g.slug AS produced_slug, g.status AS produced_status"
            " FROM strategist_decisions d"
            " LEFT JOIN goals g ON g.id = d.produced_goal_id"
            " WHERE d.batch_id = ? AND d.decision_kind = 'Inject'"
            " ORDER BY d.id",
            (batch_id,),
        ))
        out.append(f"promised batch ({len(siblings)} Inject(s)):")
        for s in siblings:
            brief_head = (s["brief"] or "").strip().split("\n", 1)[0][:70]
            if s["produced_slug"] is not None:
                tail = (f"→ `{s['produced_slug']}` "
                        f"(status={s['produced_status']})")
            else:
                tail = f"→ outcome={s['outcome'] or 'pending'}"
            out.append(f"  - {brief_head}  {tail}")
        out.append("")
    return out


def _section_active_goals(conn: sqlite3.Connection,
                          problem: str) -> list[str]:
    # Status-based filter: any non-terminal status (open / attempting /
    # pending_strategist_review). Descendants of a shelved / disproved
    # ancestor are cascade-shelved at the data layer by
    # `dispatcher._cascade_shelve_descendants`, so they drop out of
    # this status filter naturally. No view-level alive-set CTE needed:
    # the goal status IS the source of truth for "is this dispatchable".
    rows = list(conn.execute(
        "SELECT id, slug, statement, depth, status, attempts"
        " FROM goals WHERE problem = ?"
        "   AND status IN ('open','attempting','pending_strategist_review')"
        " ORDER BY depth, id",
        (problem,),
    ))
    if not rows:
        return []
    out = ["## Active goals", ""]
    for r in rows:
        # 200→400 (2026-07-05): statements are now pp-canonical
        # conclusions (decl-#1) and 200 cut many real ones mid-term —
        # the Strategist fell back to reading stub files to compare
        # goals (feedback: twin-goal hunt done by hand).
        st = str(r["statement"])
        if len(st) > 400:
            st = st[:400].rstrip() + "…"
        out.append(
            f"- [{r['id']}] depth={r['depth']} "
            f"{r['status']:25s} attempts={r['attempts']}"
            f" `{r['slug']}`"
        )
        out.append(f"  `{st}`")
    out.append("")
    return out


def _section_failure_replay(conn: sqlite3.Connection,
                            problem: str,
                            k: int = 5) -> list[str]:
    """Last `k` strategist_decisions on this problem with their
    outcomes — self-feedback signal so Strategist learns
    'what I tried, what happened'."""
    try:
        rows = list(conn.execute(
            "SELECT triggered_at_tick, trigger_kind, decision_kind,"
            " target_id, brief, reason, payload, outcome, created_at"
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
            + (f" outcome={r['outcome']}" if r['outcome'] else "")
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
            out.append(f"  brief: {brief}")
    out.append("")
    return out


def _section_plan_note(workspace: Path, problem: str) -> list[str]:
    """The Strategist's PRIVATE cross-wake plan note
    (`.drafts/strategist_plan.md`) — rendered here ONLY, never into worker
    contexts. The third channel next to the two worker-facing ones
    (standing directive broadcast / one-shot Inject brief): its curated
    world-model previously leaked into the directive and taxed every
    worker spawn. Soft cap = one warning line, nothing harder."""
    from ..pipeline import _drafts
    problem_dir = db.problem_dir(workspace, problem)
    text = _drafts.read_plan_note(problem_dir)
    if not text or not text.strip():
        return []
    out = ["## Your plan note (private, cross-wake)", ""]
    if len(text) > _drafts.PLAN_NOTE_SOFT_CAP:
        out += [f"_⚠ {len(text)} chars — past the useful size; rewrite it "
                f"down to what still matters._", ""]
    out += [text.strip(), ""]
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
        "Treat as a rolling curated document — diff-update each routine "
        "tick: keep useful entries, prune stale, append new findings.)",
        "",
        str(directive).strip(),
        "",
    ]


def _section_tree_inline(conn: sqlite3.Connection,
                         workspace: Path, problem: str) -> list[str]:
    """Inline the FRONTIER view of the proof tree for the Strategist
    (framework_backlog #2). Rendered live from the DB with
    `tree.render(frontier=True)`: settled (proved / shelved / dead /
    disproved / frozen) subtrees collapse to a single labelled line so
    the live frontier (open / attempting / pending + in-flight proposed
    strategies) is not buried under hundreds of settled nodes on a mature
    problem. The full, uncollapsed tree stays on disk in TREE.md (written
    by the dispatcher every cascade) — linked below as an escape hatch
    for inspecting any collapsed subtree.

    Rendering from the DB (not reading the precompiled TREE.md) also makes
    the inline view current as of this context build, never one cascade
    stale. Falls back to a stub note if the problem has no tree yet."""
    try:
        body = tree.render(conn, problem, frontier=True).strip()
    except Exception:
        body = ""
    # Phase 7 regression fix (sphere_homology, ~8 agent reports): the old
    # substring test `"no root goal" in body` also matched tree.py's
    # pure-NL header `_(pure-NL problem — no root goal; deliverable forest
    # below)_`, silently DISCARDING the entire deliverable-forest render
    # on every strategist wake of a pure-NL problem. The placeholder it
    # guarded against ("run `asterism init`") no longer exists — Phase 6
    # made the rootless render a real forest — so only emptiness remains.
    if not body:
        return ["## TREE", "", "(TREE.md not yet generated)", ""]
    tree_path = db.problem_dir(workspace, problem) / "TREE.md"
    try:
        rel = tree_path.relative_to(workspace).as_posix()
    except ValueError:
        rel = "TREE.md"
    return [
        "## TREE",
        "",
        body,
        "",
        f"_Frontier view (settled subtrees collapsed). Full decomposition "
        f"tree on disk: `{rel}` — read it to inspect a collapsed subtree._",
        "",
    ]


def _section_manifest_meta(mfst: manifest.Manifest,
                           workspace: Path, problem: str) -> list[str]:
    """For T0 / T3 — surface Manifest statement + Defs.lean preview so
    Strategist can decide whether RequestUserAmend on Defs.lean is needed
    (statement-vocabulary missing)."""
    out = ["## Manifest", "", "### Statement", ""]
    out.append(f"```\n{mfst.statement}\n```")
    if mfst.strategic_notes:
        out += ["", "### Strategic notes", ""]
        out.append(mfst.strategic_notes)
    defs_path = db.problem_dir(workspace, problem) / "Defs.lean"
    out += ["", "### Defs.lean", ""]
    if defs_path.exists():
        try:
            defs_text = defs_path.read_text(encoding="utf-8")
            out.append(f"```lean\n{defs_text}\n```")
        except OSError:
            out.append("(Defs.lean unreadable)")
    else:
        out.append("(Defs.lean does not exist — RequestUserAmend candidate)")
    out.append("")
    return out


def compile_strategist_context(conn: sqlite3.Connection, *,
                               problem: str, trigger_kind: str,
                               attempts_dir: Path,
                               workspace: Path,
                               mfst: manifest.Manifest,
                               pending_review_id: int | None = None,
                               ) -> Path:
    """Write Context.md for the Strategist agent into attempts_dir.

    Sections (in order, all optional if their source is empty):
      - Trigger (always; includes pending review target for T2)
      - Active goals
      - Recent decisions (failure_replay)
      - TREE
      - Manifest (T0 / T3 — when bootstrap_done=false or amend-relevant)
    """
    section_names = ["trigger"]
    sections: list[list[str]] = [
        _section_trigger(trigger_kind, pending_review_id, conn),
    ]
    # T2 review_context (Phase 2 §2.2) — failure brief + existing
    # strategies + ancestor chain. Only emitted for pending_review trigger
    # with a real target; T0 / T1 / first_launch skip these sections.
    if trigger_kind == "pending_review" and pending_review_id is not None:
        section_names += ["review_failure", "review_strategies",
                          "review_ancestors"]
        sections += [
            _section_pending_review_failure(conn, pending_review_id),
            _section_pending_review_strategies(conn, pending_review_id),
            _section_pending_review_ancestors(conn, pending_review_id),
        ]
    # Phase 2.5 — surface unack Inject batches on every trigger when
    # any exist (not gated on trigger_kind='inject_batch_done'). See
    # `_section_inject_batch_outcomes` docstring for the race rationale.
    # `_section_pending_reopens` runs on every trigger too — Strategist
    # may discover a Reopen candidate while waking on pending_review /
    # routine / inject_batch_done alike. Empirically (brouwer 2026-05-22)
    # the loop "ConfirmShelve promises retry → Forward lands → Strategist
    # never Reopens" was never closed by the agent on its own; surfacing
    # the cross-reference gives it a structured cue.
    section_names += ["stall_warning", "ingest_gate", "directive",
                      "plan_note", "inject_batches", "pending_reopens",
                      "active_goals", "failure_replay", "tree",
                      "manifest_meta", "paper_index"]
    sections += [
        _section_stall_warning(conn, problem),
        _section_ingest_gate(conn, problem),
        _section_current_directive(conn, problem),
        _section_plan_note(workspace, problem),
        _section_inject_batch_outcomes(conn, problem),
        _section_pending_reopens(conn, problem, trigger_kind),
        _section_active_goals(conn, problem),
        _section_failure_replay(conn, problem),
        _section_tree_inline(conn, workspace, problem),
        _section_manifest_meta(mfst, workspace, problem),
        context._section_paper_index(mfst, workspace),
    ]
    parts: list[str] = [f"# Strategist context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    context.write_context_stats(
        attempts_dir, label=f"strategist {problem}",
        names=section_names, sections=sections)
    return out


# ---------------------------------------------------------------------
# Forward
# ---------------------------------------------------------------------

def _section_forward_brief(conn: sqlite3.Connection,
                           decision_id: int | None) -> list[str]:
    """Strategist Inject brief — primary input to Forward. Falls back
    to a placeholder if decision_id is None / row missing (shouldn't
    happen in production but tests / replay may exercise this)."""
    if decision_id is None:
        return [
            "## Strategist brief",
            "",
            "(no Strategist Inject brief — Forward was dispatched without one. "
            "Default to a broadly useful new lemma in the problem's domain.)",
            "",
        ]
    try:
        row = conn.execute(
            "SELECT brief FROM strategist_decisions WHERE id = ?",
            (int(decision_id),),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None or not row["brief"]:
        return [
            "## Strategist brief",
            "",
            "(decision row missing brief content; treat as open-ended.)",
            "",
        ]
    return ["## Strategist brief", "", str(row["brief"]).strip(), ""]


def _section_library_inventory(conn: sqlite3.Connection,
                               problem: str) -> list[str]:
    """All proved goals in this problem (Forward's local toolkit).
    Cross-problem Library promotion is out of Phase 2 scope; just
    same-problem proved lemmas for now."""
    rows = list(conn.execute(
        "SELECT slug, statement FROM goals"
        " WHERE problem = ? AND status = 'proved'"
        " ORDER BY id",
        (problem,),
    ))
    if not rows:
        return ["## Library (proved lemmas in this problem)", "",
                "(none yet)", ""]
    out = ["## Library (proved lemmas in this problem)", ""]
    for r in rows:
        st = str(r["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        out.append(f"- `{r['slug']}`: `{st}`")
    out.append("")
    return out


def _section_forward_history(conn: sqlite3.Connection,
                             problem: str, k: int = 5) -> list[str]:
    """Previous Forward lemmas in this problem (goals.origin='forward')
    so the agent doesn't repropose the same shape."""
    rows = list(conn.execute(
        "SELECT slug, statement, status FROM goals"
        " WHERE problem = ? AND origin = 'forward'"
        " ORDER BY id DESC LIMIT ?",
        (problem, k),
    ))
    if not rows:
        return []
    out = ["## Past Forward proposals (newest first)", ""]
    for r in rows:
        st = str(r["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
        out.append(f"- `{r['slug']}` ({r['status']}): `{st}`")
    out.append("")
    return out


def compile_forward_context(conn: sqlite3.Connection, *,
                            problem: str, decision_id: int | None,
                            attempts_dir: Path,
                            workspace: Path,
                            mfst: manifest.Manifest,
                            ) -> Path:
    """Write Context.md for the Forward agent into attempts_dir.

    Sections:
      - Strategist brief (load-bearing input)
      - Library inventory
      - Past Forward proposals
      - Active goals (alive open/attempting/pending — so Forward does not
        restate one and get dedup-rejected)
      - Manifest hints (Mathlib pointers — agent uses loogle Bash for
        type-pattern search)

    NOT the full decomposition tree. Forward writes ONE generic lemma from
    the (prescriptive) brief and cites proved lemmas from `## Library`; it
    does not navigate goal structure. On a mature problem the inlined TREE
    was ~400 lines that were ~99% proved sub-trees (redundant with the
    `## Library` signatures) plus dead/shelved branches (abandoned-route
    noise) — pure context bloat that slowed the agent and diluted focus
    (framework_backlog #3). The one thing Forward uses tree state for —
    not restating an alive goal — is exactly `_section_active_goals`.
    (The Strategist context still inlines the full tree; it plans over
    the whole structure.)
    """
    section_names = ["forward_brief", "library_inventory",
                     "forward_history", "active_goals", "manifest_meta",
                     "paper_index"]
    sections: list[list[str]] = [
        _section_forward_brief(conn, decision_id),
        _section_library_inventory(conn, problem),
        _section_forward_history(conn, problem),
        _section_active_goals(conn, problem),
        _section_manifest_meta(mfst, workspace, problem),
        # Paper navigation — Forward mints the vocabulary; exact
        # hypotheses/definitions come from the paper (design D1).
        context._section_paper_index(mfst, workspace),
    ]
    parts: list[str] = [f"# Forward context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    context.write_context_stats(
        attempts_dir, label=f"forward {problem}",
        names=section_names, sections=sections)
    return out
