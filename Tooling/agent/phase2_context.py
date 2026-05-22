"""Phase 2 — Strategist + Forward Context.md compilation.

Strategist + Forward operate at problem-level, not goal-level — so
they bypass `compile_context` (which is hard-wired to a specific goal
row) and assemble Context.md from problem-level facts only.

Strategist sees:
  - `trigger_kind`
  - Active goal list with statements + status
  - Recent strategist_decisions + their outcomes (self-feedback)
  - TREE.md inline (precompiled artifact)
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

from ..state import db, manifest


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
            if len(proposal) > 1500:
                proposal = proposal[:1500].rstrip() + "\n…(truncated)"
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

    Per-step "produced lemma" lookup intentionally omitted: goals don't
    carry decision_id, so attribution would have to match by
    problem + created_at which can't disambiguate steps of the same
    batch. Strategist reads `## Library` + `## TREE` for what actually
    landed.
    """
    batch_ids = db.unacknowledged_inject_batches(conn, problem)
    if not batch_ids:
        return []
    out = ["## Completed Inject batches (newest first)", ""]
    placeholders = ",".join("?" * len(batch_ids))
    rows = list(conn.execute(
        f"SELECT id, batch_id, brief, payload, outcome, updated_at"
        f" FROM strategist_decisions"
        f" WHERE batch_id IN ({placeholders})"
        f" ORDER BY MAX(updated_at) OVER (PARTITION BY batch_id) DESC,"
        f"          batch_id, id",
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
            brief = (r["brief"] or "").strip()
            if len(brief) > 300:
                brief = brief[:300].rstrip() + "…"
            outcome_text = r["outcome"] or "(no outcome)"
            out.append(f"- **step {idx}** outcome=`{outcome_text}`")
            out.append(f"  brief: {brief}")
        out.append("")
    return out


def _section_pending_reopens(conn: sqlite3.Connection,
                             problem: str,
                             trigger_kind: str) -> list[str]:
    """Cross-reference shelved goals against Forward-origin goals proved
    since their shelve event.

    Strategist's ConfirmShelve reasons frequently promise "retry once
    the injected Forward lands" but the framework has no automatic
    re-evaluate when the promised Forward proves — empirically (brouwer
    run 2026-05-22) 7/9 ConfirmShelve reasons in this run wrote that
    kind of promise, 0 Reopen decisions followed. This section surfaces
    the candidate Reopen list so the agent can decide
    `Reopen(target_goal_id=...)` instead of injecting yet another
    toolkit piece.

    Gated on `trigger_kind == 'inject_batch_done'` — that's the wake
    type where a batch just terminated (one or more Forwards may have
    just proved), making Reopen-check most actionable. Other triggers
    (routine / pending_review / first_launch) skip this section to
    reduce per-call Context.md noise; historic promises still surface
    via the next inject_batch_done wake.

    Per shelved goal:
      * latest ConfirmShelve `reason` (truncated to ~200 chars) — the
        explicit promise the agent made when shelving;
      * Forward-origin goals that proved *after* the shelve event —
        candidate prereqs the agent can match against its own promise.

    Output omitted when trigger is not `inject_batch_done` or when
    there are no shelved goals.
    """
    if trigger_kind != "inject_batch_done":
        return []
    shelved = list(conn.execute(
        "SELECT id, slug, updated_at FROM goals"
        " WHERE problem = ? AND status = 'shelved'"
        " ORDER BY updated_at DESC LIMIT 12",
        (problem,),
    ))
    if not shelved:
        return []

    out = [
        "## Pending reopen-promises",
        "",
        "Shelved goals whose ConfirmShelve reason may have promised "
        "retry once a Forward toolkit landed. Cross-referenced against "
        "Forward-origin goals that proved since the shelve. If a "
        "shelved goal's promise matches a now-proved Forward, "
        "`Reopen(target_goal_id=<shelved_id>)` may close the loop "
        "instead of injecting another toolkit piece.",
        "",
    ]
    for g in shelved:
        gid = int(g["id"])
        slug = str(g["slug"])
        shelved_at = str(g["updated_at"])
        # Latest ConfirmShelve reason for this goal (if any).
        cs_row = conn.execute(
            "SELECT reason FROM strategist_decisions"
            " WHERE problem = ? AND decision_kind = 'ConfirmShelve'"
            "  AND target_id = ? AND reason IS NOT NULL"
            " ORDER BY id DESC LIMIT 1",
            (problem, str(gid)),
        ).fetchone()
        reason = str(cs_row["reason"]).strip() if cs_row else ""
        if reason and len(reason) > 220:
            reason = reason[:220].rstrip() + "…"
        # Forward-origin goals proved AFTER this shelve.
        fwd_rows = list(conn.execute(
            "SELECT slug FROM goals"
            " WHERE problem = ? AND origin = 'forward' AND status = 'proved'"
            "  AND updated_at > ?"
            " ORDER BY updated_at",
            (problem, shelved_at),
        ))
        fwd_slugs = [str(r["slug"]) for r in fwd_rows]

        out.append(f"### `{slug}` (id={gid}, shelved {shelved_at[:19]})")
        if reason:
            out.append(f"shelve reason: {reason}")
        else:
            out.append("shelve reason: (no ConfirmShelve decision recorded — "
                       "framework shelve, not Strategist-confirmed)")
        if fwd_slugs:
            joined = ", ".join(f"`{s}`" for s in fwd_slugs)
            out.append(f"Forwards proved since shelve ({len(fwd_slugs)}): "
                       f"{joined}")
        else:
            out.append("Forwards proved since shelve: (none yet)")
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
        st = str(r["statement"])
        if len(st) > 200:
            st = st[:200].rstrip() + "…"
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


def _section_tree_inline(workspace: Path, problem: str) -> list[str]:
    """Inline the problem's TREE.md (precompiled artifact). If absent
    (fresh problem post-init), return a stub note."""
    tree_path = db.problem_dir(workspace, problem) / "TREE.md"
    if not tree_path.exists():
        return ["## TREE", "", "(TREE.md not yet generated)", ""]
    try:
        text = tree_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ["## TREE", "", "(TREE.md unreadable)", ""]
    return ["## TREE", "", text, ""]


def _section_manifest_meta(mfst: manifest.Manifest,
                           workspace: Path, problem: str) -> list[str]:
    """For T0 / T3 — surface Manifest statement + hints + Defs.lean
    preview so Strategist can decide whether RequestUserAmend on Defs.lean
    is needed (statement-vocabulary missing)."""
    out = ["## Manifest", "", "### Statement", ""]
    out.append(f"```\n{mfst.statement}\n```")
    if mfst.all_hints:
        out += ["", "### Lemma hints", ""]
        for h in mfst.all_hints:
            out.append(f"- {h}")
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
    sections: list[list[str]] = [
        _section_trigger(trigger_kind, pending_review_id, conn),
    ]
    # T2 review_context (Phase 2 §2.2) — failure brief + existing
    # strategies + ancestor chain. Only emitted for pending_review trigger
    # with a real target; T0 / T1 / first_launch skip these sections.
    if trigger_kind == "pending_review" and pending_review_id is not None:
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
    sections += [
        _section_inject_batch_outcomes(conn, problem),
        _section_pending_reopens(conn, problem, trigger_kind),
        _section_active_goals(conn, problem),
        _section_failure_replay(conn, problem),
        _section_tree_inline(workspace, problem),
        _section_manifest_meta(mfst, workspace, problem),
    ]
    parts: list[str] = [f"# Strategist context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
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
      - TREE.md inline (problem structure)
      - Manifest hints (Mathlib pointers — agent uses loogle Bash for
        type-pattern search)
    """
    sections: list[list[str]] = [
        _section_forward_brief(conn, decision_id),
        _section_library_inventory(conn, problem),
        _section_forward_history(conn, problem),
        _section_tree_inline(workspace, problem),
        _section_manifest_meta(mfst, workspace, problem),
    ]
    parts: list[str] = [f"# Forward context — {problem}", ""]
    for sect in sections:
        parts.extend(sect)
    out = attempts_dir / "Context.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out
