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
import re
import sqlite3
from pathlib import Path

from ..state import db, manifest, tree
from . import context

# Inline tail of the proved catalog (strategist index + Forward
# library): the freshness floor against a stale plan note / brief.
# Full list lives in the CATALOG.md companion.
_CATALOG_RECENT_N = 25


# ---------------------------------------------------------------------
# Strategist
# ---------------------------------------------------------------------

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


def _section_disproof_guidance(conn: sqlite3.Connection,
                               problem: str) -> list[str]:
    """Feature D — context-conditional falsity triage. Rendered only
    when the problem shows falsity signals (a `disproved` goal, an
    `agent_infeasible` decline, or an AttemptDisproof in flight /
    settled), so healthy problems never see it (prompt stays static).
    """
    signals = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM goals WHERE problem = ? AND"
        "  status = 'disproved')"
        " OR EXISTS(SELECT 1 FROM strategist_decisions WHERE problem = ?"
        "  AND decision_kind = 'AttemptDisproof')",
        (problem, problem)).fetchone()[0]
    if not signals:
        return []
    lines = [
        "## Falsity triage",
        "",
        "A goal here is believed false. Triage before spending:",
        "- Looks like a USER TYPO (sign/bound/quantifier plainly "
        "misstated) → `RequestUserAmend` with the suggested fix; don't "
        "burn compute disproving a typo.",
        "- STRUCTURAL doubt about a user-requested claim "
        "(counterexample sketch, failing special case) → "
        "`{\"kind\": \"AttemptDisproof\", \"target_goal_id\": <id>, "
        "\"reason\": \"<the evidence>\"}` — the framework mints the "
        "mechanical ¬ goal; the kernel settles it, not belief.",
        "- Merely HARD → keep proving; difficulty is not falsity.",
        "- Inner (non-deliverable) sub-goals believed false usually "
        "mean the DECOMPOSITION is wrong — re-decompose, don't disprove.",
        "",
    ]
    settled = conn.execute(
        "SELECT d.target_id AS t, gn.slug AS ns, gp.slug AS ps,"
        " gp.status AS ts"
        " FROM strategist_decisions d"
        " JOIN goals gn ON gn.id = d.produced_goal_id"
        " JOIN goals gp ON gp.id = d.target_id"
        " WHERE d.problem = ? AND d.decision_kind = 'AttemptDisproof'"
        " AND gn.status = 'proved'", (problem,)).fetchall()
    for row in settled:
        lines += [
            f"SETTLED FALSE: `{row['ps']}` — its negation `{row['ns']}` "
            f"is kernel-proved. `Ingest` is blocked while the target is "
            f"pursued: `RequestUserAmend` to hand the disproof back to "
            f"the user (attach `{row['ns']}`), or retire the target if "
            f"the user already amended.",
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


def _slugify_ident(name: str) -> str:
    """camelCase / PascalCase → snake_case, primes dropped — the slug
    charset normalization ([a-z][a-z0-9_]*) workers apply when a brief
    pins a name the commit gate would reject."""
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return s.lower().replace("'", "")


def _section_inject_batch_outcomes(conn: sqlite3.Connection,
                                   problem: str,
                                   workspace: "Path | None" = None,
                                   ) -> list[str]:
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
    # Worker declines since the last wake (user call 2026-07-19): the
    # mathematical WHY of a mid-flight decline (parent_needs_fix
    # counterexamples, no_progress / circularity analyses) lived only in
    # per-goal surfaces, so a cousin branch re-invented a refuted
    # statement before any steering surface ever showed it (b6_1
    # growth_exponent re-mint). Rendered on the batch scoreboard — the
    # one wall the strategist already reads — bounded to 5 entries.
    decline_lines = _recent_decline_lines(conn, problem)
    batch_ids = db.unacknowledged_inject_batches(conn, problem)
    if not batch_ids:
        return decline_lines
    out = ["## Completed Inject batches (newest first)", ""]
    placeholders = ",".join("?" * len(batch_ids))
    # Inject rows only: every wake's decisions share the batch_id, so
    # ConfirmShelve/EmitDirective siblings used to render as brief-less
    # phantom "step 0" rows (agent_feedback 2026-07-11..13).
    rows = list(conn.execute(
        f"SELECT d.id, d.batch_id, d.brief, d.payload, d.outcome,"
        f" d.outcome_detail, d.updated_at, d.produced_kind,"
        f" g.slug AS landed_slug, g.status AS landed_status,"
        f" g.statement AS landed_statement, g.lean_path AS landed_path"
        f" FROM strategist_decisions d"
        f" LEFT JOIN goals g ON g.id = d.produced_goal_id"
        f" WHERE d.batch_id IN ({placeholders})"
        f"   AND d.decision_kind = 'Inject'"
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
            kind = str(r["produced_kind"] or "")
            if r["landed_slug"]:
                # Full signature off the landed file when reachable
                # (07-29: the DB statement is the RESULT TYPE for a def
                # — `— Prop` — which cannot establish arity; the arity
                # dispute fueled a five-round verdict war).
                stmt = ""
                if workspace is not None and r["landed_path"]:
                    try:
                        from .context import _catalog_signature
                        stmt = " ".join((_catalog_signature(
                            workspace, str(r["landed_path"]),
                            str(r["landed_slug"])) or "").split())
                    except Exception:  # noqa: BLE001 — cosmetic only
                        stmt = ""
                if not stmt:
                    stmt = " ".join(str(r["landed_statement"] or "").split())
                if len(stmt) > 300:
                    stmt = stmt[:300].rstrip() + "…"
                # v32 attribution: say HOW the artifact relates to the
                # brief instead of making the Strategist guess (#3 —
                # the success-without-landing / renamed-landing pair).
                if kind == "reuse":
                    out.append(
                        f"  REPOINTED to existing goal "
                        f"`{r['landed_slug']}` "
                        f"(status={r['landed_status']}) — nothing new "
                        f"was minted; your statement matched it")
                elif kind == "alias":
                    out.append(
                        f"  landed as ALIAS: `{r['landed_slug']}` "
                        f"(status={r['landed_status']})"
                        + (f" — `{stmt}`" if stmt else "")
                        + " — an existing decl carries the content; "
                          "cite this slug")
                elif kind == "redispatch":
                    settled_note = (
                        " — CAUTION: outcome=`superseded` means the "
                        "target settled via ANOTHER route, not your "
                        "briefed decomposition"
                        if str(r["outcome"] or "") == "superseded"
                        else "")
                    out.append(
                        f"  redispatch of goal `{r['landed_slug']}` "
                        f"(status={r['landed_status']})" + settled_note)
                else:
                    out.append(
                        f"  landed: `{r['landed_slug']}` "
                        f"(status={r['landed_status']})"
                        + (f" — `{stmt}`" if stmt else ""))
                    # Delivered-vs-briefed (a5 run: `outcome=success`
                    # read as "the brief was delivered" while the worker
                    # had shipped a different declaration; the
                    # strategist kept a hand tally to compensate). The
                    # UNTRUNCATED brief never naming the landed slug is
                    # the mechanical tell.
                    full_brief = str(r["brief"] or "")
                    slug = str(r["landed_slug"])
                    if full_brief and not re.search(
                            rf"\b{re.escape(slug)}\b", full_brief):
                        # 07-29: a briefed camelCase name whose slug
                        # normalization equals the landed slug is a
                        # RENAME the framework can attribute itself —
                        # the bare RETARGETED flag cost a full batch of
                        # forensics + an adversary round for a
                        # mechanically-derivable fact.
                        briefed = next(
                            (m for m in re.findall(
                                r"`([A-Za-z][A-Za-z0-9_']*)`", full_brief)
                             if _slugify_ident(m) == slug), None)
                        if briefed:
                            out.append(
                                f"  RENAMED: briefed `{briefed}` landed "
                                f"as `{slug}` — the slug charset is "
                                "[a-z0-9_], the worker normalized the "
                                "name; statement otherwise as briefed "
                                "unless the signature above disagrees")
                        else:
                            out.append(
                                "  RETARGETED: the brief never names this "
                                "declaration — the worker delivered under a "
                                "different name/statement than briefed; "
                                "diff it against the brief before building "
                                "on it")
            elif str(r["outcome"] or "") in ("success", "proved"):
                out.append(
                    "  landed: (nothing attributed to this step — the "
                    "brick may have landed renamed/merged; grep "
                    "CATALOG.md before treating it as landed)")
            out.append(f"  brief: {brief}")
            detail = (r["outcome_detail"] or "").strip()
            if detail:
                if len(detail) > 1200:
                    detail = detail[:1200].rstrip() + "…"
                out.append(f"  why: {detail}")
        out.append("")
    out.extend(decline_lines)
    return out


_DECLINE_REASONS_SURFACED = (
    "parent_needs_fix", "agent_declined", "no_progress",
    "circular_decomposition",
)


def _recent_decline_lines(conn: sqlite3.Connection,
                          problem: str, k: int = 5) -> list[str]:
    """`### Worker declines since your last wake` — goal slug + the
    decline's own reasoning (proposal_md carries the math; the
    failure_detail for a decline is just the routing enum). Windowed to
    dead_attempts newer than the problem's last strategist decision
    (first wake: last 24h of rows), capped at `k`."""
    try:
        since = conn.execute(
            "SELECT MAX(created_at) FROM strategist_decisions"
            " WHERE problem = ?", (problem,)).fetchone()[0]
        marks = ",".join("?" * len(_DECLINE_REASONS_SURFACED))
        sql = (f"SELECT da.failure_reason, da.failure_detail,"
               f" da.proposal_md, g.slug"
               f" FROM dead_attempts da JOIN goals g ON g.id = da.target_id"
               f" WHERE da.target_kind = 'Goal' AND g.problem = ?"
               f"   AND da.failure_reason IN ({marks})")
        args: list = [problem, *_DECLINE_REASONS_SURFACED]
        if since:
            # >= not >: a decline landing the same clock tick as the
            # wake's own commit must not vanish (Windows timestamp
            # granularity); an exact-boundary repeat is harmless.
            sql += " AND da.ts >= ?"
            args.append(since)
        rows = conn.execute(
            sql + " ORDER BY da.id DESC LIMIT ?", (*args, k)).fetchall()
    except sqlite3.OperationalError:
        return []
    if not rows:
        return []
    out = ["### Worker declines since your last wake",
           "_A decline's reasoning is evidence about statements in your"
           " roadmap — a refuted formulation stays refuted under a new"
           " slug._", ""]
    for r in rows:
        why = " ".join((r["proposal_md"] or r["failure_detail"] or "")
                       .replace("--", " ").split())
        if len(why) > 250:
            why = why[:250].rstrip() + "…"
        out.append(f"- `{r['slug']}` [{r['failure_reason']}]: {why}")
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
    own promised batch (the one cited by their promise-bearing
    ConfirmShelve — the first since the goal's latest Reopen) is now
    complete — i.e., goals where the Inject(s) Strategist explicitly
    designed to address them have produced their outcomes and there's
    now genuine new evidence to re-evaluate.

    Fortuitous unblock (a Forward designed for an unrelated batch
    happens to make a shelved goal provable) is handled separately by
    the G1 dedupe revival pass (`find_shelved_revivals_for_forward` →
    `_revive_shelved_alias`) — no need to re-surface unrelated
    shelved goals here.

    Per surfaced goal:
      * the promise-bearing ConfirmShelve's `reason` (the explicit
        promise);
      * the now-complete promised batch's Inject decisions + their
        produced goals (so Strategist sees exactly what landed).
    """
    if trigger_kind != "inject_batch_done":
        return []

    # Find shelved goals whose PROMISE-BEARING ConfirmShelve was
    # committed in a batch whose every sibling Inject row has `outcome
    # IS NOT NULL` (batch fully terminal). Promise-bearing = the FIRST
    # ConfirmShelve since the goal's latest Reopen (or first ever) —
    # that's the one the verifier forced to pair with a compensating
    # Inject. Later re-confirms are terminal answers, not new promises:
    # every wake's decisions share one batch_id, so a standalone
    # re-confirm co-batched with an UNRELATED forced-advance Inject
    # used to read as a fresh pairing and re-arm this section every
    # wake (agent_feedback 2026-07-14, goal 5941 — 15 reports).
    rows = list(conn.execute(
        """
        WITH latest_cs AS (
            SELECT g.id AS goal_id, g.slug AS goal_slug,
                   g.updated_at AS shelved_at,
                   MIN(d.id) AS cs_decision_id
            FROM goals g
            JOIN strategist_decisions d
              ON d.target_id = CAST(g.id AS TEXT)
             AND d.decision_kind = 'ConfirmShelve'
             AND d.problem = g.problem
             AND d.batch_id IS NOT NULL
             AND d.id > COALESCE((
                 SELECT MAX(r.id) FROM strategist_decisions r
                 WHERE r.problem = g.problem
                   AND r.target_id = CAST(g.id AS TEXT)
                   AND r.decision_kind = 'Reopen'
             ), 0)
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
    out = ["## Active goals", ""]
    for r in rows:
        # 200→400 (2026-07-05): statements are now pp-canonical
        # conclusions (decl-#1) and 200 cut many real ones mid-term —
        # the Strategist fell back to reading stub files to compare
        # goals (feedback: twin-goal hunt done by hand).
        # #5 (2026-07-18): display the FULL signature from the stub
        # file — the stored conclusion-only column renders a by_contra
        # sub-goal as just `False`.
        st = context.goal_display_signature(
            workspace, str(r["slug"]), r["lean_path"], r["statement"])
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
        # A failed decision's WHY (FetchPaper unfetchable detail, a dead
        # redispatch's forensics) — without it the replay teaches only
        # THAT it failed, and the same move gets re-tried blind.
        if (str(r["outcome"] or "").startswith("failed")
                and (r["outcome_detail"] or "").strip()):
            why = " ".join(str(r["outcome_detail"]).split())
            if len(why) > 200:
                why = why[:200] + "…"
            out.append(f"  why: {why}")
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
        return ["## TREE", "", "(no goals yet)", ""]
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
    exceptions = [r for r in rows if str(r["status"]) != "proved"]
    if exceptions:
        out.append("_Non-proved goals:_")
        for r in exceptions:
            att = (f", attempts={r['attempts']}"
                   if r["attempts"] else "")
            out.append(f"- `{r['slug']}`  ({r['status']}{att})")
        out.append("")
    out += [
        f"_Full decomposition tree: `{rel}` (dispatcher-maintained, "
        f"current every cascade) — read it for structure, dead-branch "
        f"forensics, and OR-alternative history._",
        "",
    ]
    return out


def _section_manifest_meta(mfst: manifest.Manifest,
                           workspace: Path, problem: str) -> list[str]:
    """For T0 / T3 — surface Manifest statement + Defs.lean preview so
    Strategist can decide whether RequestUserAmend on Defs.lean is needed
    (statement-vocabulary missing). An ABSENT Defs.lean renders nothing:
    pure-NL problems have none by design (Phase 6), and the old
    placeholder ("does not exist — RequestUserAmend candidate") was a
    standing lure that mislabelled the legal state as a defect with a
    human-escalation hint attached (user call 2026-07-13)."""
    out = ["## Manifest", "", "### Statement", ""]
    out.append(f"```\n{mfst.statement}\n```")
    if mfst.strategic_notes:
        out += ["", "### Strategic notes", ""]
        out.append(mfst.strategic_notes)
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


def _section_paper_index_strategist(mfst: manifest.Manifest,
                                    workspace: Path,
                                    conn=None,
                                    attempts_dir: "Path | None" = None,
                                    ) -> list[str]:
    """Strategist view of the paper section: the shared navigation
    block + the provenance-recording instruction + the FetchPaper
    channel (conditional — only a paper-bound problem renders them;
    prompt stays static per the prompt-editing principle)."""
    lines = context._section_paper_index(mfst, workspace, conn,
                                         attempts_dir=attempts_dir)
    if not lines:
        return lines
    return lines + [
        "Every `MarkDeliverable` on this problem MUST include "
        "`paper_ref: \"p.N <label>\"` in its payload (where the paper "
        "states the claim) — it is shown to the human at sign-off.",
        "When the paper cites a work you genuinely need (a proof "
        "detail this paper omits), decide "
        "`{\"kind\": \"FetchPaper\", \"query\": \"<citation as "
        "printed>\", \"reason\": \"<why>\"}` — a Scholar agent "
        "resolves and fetches it; fetched papers appear under "
        "`### Auxiliary papers` on later wakes.",
        "",
    ]


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
        _section_trigger(trigger_kind, pending_review_id, conn,
                 workspace),
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
    section_names += ["stall_warning", "ingest_gate", "disproof_guidance",
                      "programme", "directive",
                      "plan_note", "inject_batches", "pending_reopens",
                      "active_goals", "failure_replay", "tree", "catalog",
                      "manifest_meta", "paper_index"]
    sections += [
        _section_stall_warning(conn, problem),
        _section_ingest_gate(conn, problem),
        _section_disproof_guidance(conn, problem),
        _section_programme_strategist(conn, problem),
        _section_current_directive(conn, problem),
        _section_plan_note(workspace, problem),
        _section_inject_batch_outcomes(conn, problem, workspace=workspace),
        _section_pending_reopens(conn, problem, trigger_kind),
        _section_active_goals(conn, workspace, problem),
        _section_failure_replay(conn, problem),
        _section_tree_inline(conn, workspace, problem),
        _section_catalog_index_strategist(conn, problem, attempts_dir),
        _section_manifest_meta(mfst, workspace, problem),
        _section_paper_index_strategist(mfst, workspace, conn,
                                        attempts_dir=attempts_dir),
    ]
    if trigger_kind == "routine":
        # Curation surface for the kb_curation.json sidecar — only the
        # routine wake gets it (the power is structurally routine-only;
        # moved from the retired audit wake 2026-07-25).
        section_names.append("kb_lessons")
        sections.append(
            _section_kb_lessons_curation(conn, problem, attempts_dir))
    parts: list[str] = [f"# Strategist context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    context.write_context_stats(
        attempts_dir, label=f"strategist {problem}",
        names=section_names, sections=sections)
    return out


def _section_programme_strategist(conn: sqlite3.Connection,
                                  problem: str) -> list[str]:
    """Research mode (research_mode_design.md §2): the current
    Programme rev inline — it is the commitment object your proposal
    revises (route/planning lives HERE, not in the plan note) — plus
    the Adversary's reservations on it, and, after a discarded cycle,
    the one-line rejection record (never the failed draft)."""
    import json as _json
    from ..state import programme as _programme
    try:
        row = _programme.current_rev(conn, problem)
        notice = _programme.rejection_notice(conn, problem)
    except sqlite3.OperationalError:
        return []
    out: list[str] = []
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
        reservations = verdict.get("reservations") or []
        if reservations:
            out += ["Adversary reservations on this rev:"]
            out += [f"- {r}" for r in reservations]
            out.append("")
    if notice:
        out += ["### Previous proposal rejected", "", notice, ""]
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
        f" `{context.CATALOG_COMPANION}` (read-only companion beside"
        " this Context.md, machine-generated from what actually landed"
        " — never drifts from pipeline renames; grep it by slug; every"
        " worker gets its own copy beside its Context.md, so cite it by"
        " bare name in briefs). Copy signatures from there into"
        " briefs/directives instead of hand-maintaining a catalog."
        f" The {len(recent)} newest:_",
        "",
    ]
    out += [f"- `{r['slug']}`" for r in recent]
    out.append("")
    return out


def _section_kb_lessons_curation(conn: sqlite3.Connection, problem: str,
                                 attempts_dir: Path) -> list[str]:
    """Routine-wake curation surface (2026-07-13; audit wake retired
    into routine 2026-07-25): the problem's GLOBAL lesson index — the
    same `[id-N] title` cue lines every worker sees — with full bodies
    in the `LESSONS.md` companion so the wake can adjudicate broken /
    superseded / duplicate entries and emit `kb_curation.json`.
    Lessons only: antipatterns are node-scoped and mechanically
    captured, outside the curation mandate."""
    from ..state import kb
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


def _section_library_inventory(conn: sqlite3.Connection, problem: str,
                               attempts_dir: Path) -> list[str]:
    """All proved goals in this problem (Forward's local toolkit).
    Slug index + `CATALOG.md` companion (2026-07-13, user call): at 147
    proved bricks the inline truncated statements were 17KB of every
    Forward context — slugs stay inline as the cue, exact statements
    move to the machine-generated companion (same lazy pattern as
    lessons). Header kept verbatim: forward.md points at `## Library`.
    Cross-problem Library promotion is out of Phase 2 scope; just
    same-problem proved lemmas for now."""
    rows = context.write_catalog_companion(conn, problem, attempts_dir)
    header = "## Library (proved lemmas in this problem)"
    if not rows:
        return [header, "", "(none yet)", ""]
    # Recent tail only (2026-07-14, user call — same cut as the
    # Strategist index): the brief names the bricks to use; the inline
    # list only needs to cover what the brief may predate.
    recent = rows[-_CATALOG_RECENT_N:]
    out = [
        header,
        f"_{len(rows)} proved bricks — full list & exact statements in"
        f" `{context.CATALOG_COMPANION}` (read-only companion beside"
        " this Context.md; grep it by slug). Read an entry there BEFORE"
        f" citing it or proposing anything similar."
        f" The {len(recent)} newest:_",
        "",
    ]
    out += [f"- `{r['slug']}`" for r in recent]
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
                     "manifest_forbidden", "paper_index"]
    sections: list[list[str]] = [
        _section_forward_brief(conn, decision_id),
        _section_library_inventory(conn, problem, attempts_dir),
        _section_forward_history(conn, problem),
        _section_active_goals(conn, workspace, problem),
        _section_manifest_meta(mfst, workspace, problem),
        # Dropped in the v33 merge: mint.md says "Never use any name in
        # FORBIDDEN_LEMMAS" but no section carried the list — a 07-29 SG
        # worker burned two blocked Bash calls hunting the file, and on
        # benchmark problems the ban is load-bearing. Renders "(none)"
        # when empty by design.
        context._section_manifest_forbidden(mfst),
        # Paper navigation — Forward mints the vocabulary; exact
        # hypotheses/definitions come from the paper (design D1).
        context._section_paper_index(mfst, workspace, conn,
                                     attempts_dir=attempts_dir),
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
