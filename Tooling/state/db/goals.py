from __future__ import annotations

import sqlite3

from .core import now


# ---------------------------------------------------------------------
# Goal helpers
# ---------------------------------------------------------------------

def insert_goal(conn: sqlite3.Connection, *, problem: str, slug: str,
                lean_path: str, statement: str, origin: str,
                depth: int = 0,
                kind: str = 'theorem',
                status: str = 'open') -> int:
    ts = now()
    # origin='forward' goals have no parent strategy edge; they are alive
    # only through the `detached` flag (alive-CTE seed = root ∪ detached ∪
    # strategy descendants). Written in the SAME INSERT — previously every
    # Forward commit path had to remember a follow-up `set_goal_detached`
    # (duplicated-by-discipline; a forgotten pairing is a SILENT stuck goal
    # only the offline drift-check predicate catches — 2026-07-04
    # convention audit, finding 2). `set_goal_detached` remains for
    # revive/reopen of EXISTING goals.
    detached = 1 if origin == "forward" else 0
    cur = conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement,"
        " kind, origin, status, depth, attempts, detached,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
        (problem, slug, lean_path, statement,
         kind, origin, status, depth, detached, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_goal(conn: sqlite3.Connection, goal_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()


def set_alias_target(conn: sqlite3.Connection, goal_id: int,
                     target_id: int) -> None:
    """Record that `goal_id` is an alias whose proof delegates
    to `target_id`'s file. The alias chain stays flat: if `target_id`
    is itself an alias, its own alias_target_id is followed transparently
    by the caller before passing in (see _resolve_alias_root in dedupe)."""
    conn.execute(
        "UPDATE goals SET alias_target_id = ?, updated_at = ?"
        " WHERE id = ?",
        (target_id, now(), goal_id),
    )
    conn.commit()


def aliases_pointing_at(conn: sqlite3.Connection,
                        target_id: int) -> list[int]:
    """Return ids of every goal whose alias_target_id == target_id.
    Used by prune.is_retained to keep an orphan canonical alive while
    any live goal aliases to it."""
    return [int(r["id"]) for r in conn.execute(
        "SELECT id FROM goals WHERE alias_target_id = ?", (target_id,)
    ).fetchall()]


def update_goal_status(conn: sqlite3.Connection, goal_id: int,
                       status: str, *, event: str = "",
                       reason: str = "") -> None:
    """Write a goal's status and append the transition to `goal_events`.

    The append lives HERE, at the write chokepoint, not at the
    validating one (`transitions.apply_goal_transition`): that one
    misses `amend.py`'s operator escape hatch, which flips a rewritten
    root back to 'frozen' from whatever state it was in — an edge
    `GOAL_EDGES` does not allow (only open→frozen is legal), so routing
    it through the validator is not an option. Writing from the sink
    means coverage rides the lint ratchet that already forbids raw
    status SQL, and a future caller is logged without anyone
    remembering to wire it.

    `event` / `reason` are the caller's forensic label; both default to
    empty so no call site is forced to have one.

    Same transaction as the UPDATE, and deliberately not wrapped in a
    try/except: an append-only log that silently drops rows is worse for
    forensics than no log, and an INSERT that fails here means the DB is
    already broken — in which case the status change should not stand
    either.
    """
    at = now()
    prior = conn.execute(
        "SELECT status, problem FROM goals WHERE id = ?", (goal_id,),
    ).fetchone()
    # Leaving 'proved' (rollback, manual reset) invalidates any prior
    # axiom_probe pass — clear integrity_verified in the same UPDATE so
    # the dispatcher gate picks the root up again on the next tick.
    # No-op for rows that were never verified (still 0).
    if status == 'proved':
        conn.execute(
            "UPDATE goals SET status = ?, updated_at = ? WHERE id = ?",
            (status, at, goal_id),
        )
    else:
        conn.execute(
            "UPDATE goals SET status = ?, integrity_verified = 0,"
            " updated_at = ? WHERE id = ?",
            (status, at, goal_id),
        )
    if prior is not None:
        conn.execute(
            "INSERT INTO goal_events (goal_id, problem, from_status,"
            " to_status, event, reason, at) VALUES (?,?,?,?,?,?,?)",
            (goal_id, str(prior["problem"]), str(prior["status"]),
             status, event, reason, at),
        )
    conn.commit()


def set_integrity_verified(conn: sqlite3.Connection, goal_id: int) -> None:
    """Mark a proved root as having passed `root_integrity_gate`. The
    flag stays set until `update_goal_status` flips the goal off
    'proved' (cascade rollback path)."""
    conn.execute(
        "UPDATE goals SET integrity_verified = 1, updated_at = ?"
        " WHERE id = ?",
        (now(), goal_id),
    )
    conn.commit()


def unverified_proved_roots(conn: sqlite3.Connection) -> list[str]:
    """Problems whose root is `proved` but `integrity_verified = 0`.
    Replaces the per-tick `for problem_name in manifests` scan that
    used to drive `verify.root_integrity_gate`. Ordering is by goals.id
    so iteration is deterministic across ticks."""
    return [str(r["problem"]) for r in conn.execute(
        "SELECT problem FROM goals"
        " WHERE origin = 'root' AND status = 'proved'"
        "   AND integrity_verified = 0"
        " ORDER BY id"
    ).fetchall()]


def set_goal_detached(conn: sqlite3.Connection, goal_id: int,
                      detached: bool = True) -> None:
    """Phase 2 — Strategist Reopen sets `detached=1` when the goal's
    upward strategy chain is broken (any ancestor strategy ∈ {dead,
    superseded}). BFS then dispatches on the goal standalone via the
    `open_goals` recursive CTE's `detached=1` seed. Reset to 0 by
    `update_goal_status` flipping non-'attempting' status (cascade
    rollback would otherwise leave stale detach flag)."""
    conn.execute(
        "UPDATE goals SET detached = ?, updated_at = ? WHERE id = ?",
        (1 if detached else 0, now(), goal_id),
    )
    conn.commit()


def mark_deliverable(conn: sqlite3.Connection, goal_id: int,
                     is_deliverable: bool = True) -> None:
    """anchor+claim architecture — flag a goal as a top-level
    *deliverable* (a claim or a delivered def the Strategist deems
    terminal-worthy). `asterism review` computes each deliverable's
    kernel anchor closure for human opt-out review. Sole writer of
    `goals.is_deliverable`; independent of origin/status (any node —
    Forward lemma, Backward sub-goal, or root — may be marked)."""
    conn.execute(
        "UPDATE goals SET is_deliverable = ?, updated_at = ? WHERE id = ?",
        (1 if is_deliverable else 0, now(), goal_id),
    )
    conn.commit()


def bind_paper(conn: sqlite3.Connection, *, problem: str, paper_id: str,
               origin: str, reason: str | None = None) -> bool:
    """Bind a shelved paper to a problem (paper pipeline v2, D13).
    Idempotent: an existing (problem, paper_id) binding is left as-is
    (first origin wins — a manifest binding is not demoted by a later
    scholar fetch). Returns True iff a new binding was inserted."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO problem_papers"
        " (problem, paper_id, origin, reason, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (problem, paper_id, origin, reason, now()))
    conn.commit()
    return cur.rowcount > 0


def unbind_paper(conn: sqlite3.Connection, *, problem: str,
                 paper_id: str) -> bool:
    """Remove one (problem, paper) binding — the UI's uncheck. The
    shelf entry itself is untouched. Returns True iff a row existed."""
    cur = conn.execute(
        "DELETE FROM problem_papers WHERE problem = ? AND paper_id = ?",
        (problem, paper_id))
    conn.commit()
    return cur.rowcount > 0


def paper_bindings(conn: sqlite3.Connection,
                   problem: str) -> list[sqlite3.Row]:
    """A problem's paper bindings, manifest-origin first then by age —
    the Context section treats the first row as the primary paper."""
    return conn.execute(
        "SELECT * FROM problem_papers WHERE problem = ?"
        " ORDER BY CASE origin WHEN 'manifest' THEN 0"
        " WHEN 'user' THEN 1 ELSE 2 END, created_at, paper_id",
        (problem,)).fetchall()


def scholar_fetch_count(conn: sqlite3.Connection, problem: str) -> int:
    """Scholar-origin bindings for `problem` — the D15 per-problem
    fetch-cap counter."""
    return int(conn.execute(
        "SELECT COUNT(*) FROM problem_papers"
        " WHERE problem = ? AND origin = 'scholar'",
        (problem,)).fetchone()[0])


def top_group_id(conn: sqlite3.Connection,
                 problem: str) -> "int | None":
    """The problem's top group — the one that faces the human.

    `parent_group_id IS NULL` was spelled inline in four places before
    2026-08-13, which is three more than a fact should have. None means
    the problem predates groups; callers treat that as "no scoping
    possible" and see everything, which is what those problems always
    showed.
    """
    row = conn.execute(
        "SELECT id FROM groups WHERE problem = ?"
        "   AND parent_group_id IS NULL ORDER BY id LIMIT 1",
        (problem,)).fetchone()
    return int(row["id"]) if row else None


def deliverables(conn: sqlite3.Connection,
                 problem: str | None = None,
                 group_id: "int | None" = None) -> list[sqlite3.Row]:
    """Goals flagged `is_deliverable=1`, optionally scoped to one
    problem, ordered by id. The review surface for the anchor+claim
    flow.

    v35 — `group_id` narrows to the deliverables THAT group marked.
    `is_deliverable` stays a plain "somebody marked it"; whose it is
    comes from the `MarkDeliverable` decision, the same derivation goal
    ownership uses.

    WHICH CALLERS SCOPE, AND WHY (2026-08-13, user ruling). Only the top
    group talks to the human; a sub-group's Mark is a result handed UP
    to its parent to track, not a claim addressed to anybody outside.
    So the surfaces that exist for a person scope to
    `top_group_id(problem)`:

      * `quality/review.py` — the sign-off page. Unscoped it asked the
        human to vouch for 23 of union_closed's 24 deliverables that
        were internal hand-offs between sub-groups.
      * `core/cli._find_reject_victims` — its companion: a person can
        only reject a claim they were shown.
      * `pipeline/librarian/run` — harvest seeds. The Library is
        curated FOR people, so what reaches it is what the top group
        promoted. A sub-group result not promoted is scaffolding.

    And which do NOT, because the premise above does not hold for them:

      * `pipeline/strategist` (the Ingest gate's existence check) asks
        "did this problem produce anything at all", a question about
        the machine's work rather than the human's reading list.
      * `agent/phase2_context` already passes an explicit sub-group id;
        that IS the sub-group's own hand-off summary.

    This paragraph exists because the version above it read as an
    unconditional instruction, and following it everywhere would have
    silently cut 21 proved bricks out of harvest — a display bug is
    annoying, a harvest bug loses finished work.
    """
    if group_id is not None:
        return conn.execute(
            "SELECT g.* FROM goals g WHERE g.is_deliverable = 1"
            "  AND g.problem = ? AND EXISTS ("
            "    SELECT 1 FROM strategist_decisions d"
            "     WHERE d.decision_kind = 'MarkDeliverable'"
            "       AND d.target_id = g.id AND d.group_id = ?)"
            " ORDER BY g.id", (problem, int(group_id))).fetchall()
    if problem is None:
        return conn.execute(
            "SELECT * FROM goals WHERE is_deliverable = 1 ORDER BY id"
        ).fetchall()
    return conn.execute(
        "SELECT * FROM goals WHERE is_deliverable = 1 AND problem = ?"
        " ORDER BY id",
        (problem,),
    ).fetchall()


def set_ingest_signoff_pending(conn: sqlite3.Connection, problem: str,
                               pending: bool = True) -> None:
    """anchor+claim (v14) — set/clear the per-problem ingest sign-off
    pause. Set by a Strategist `Ingest` under `library.require_signoff`;
    cleared by `asterism approve-ingest` (→ enqueue Librarian) or
    `asterism reject-ingest` (→ back to proving)."""
    conn.execute(
        "UPDATE problems SET ingest_signoff_pending = ? WHERE name = ?",
        (1 if pending else 0, problem),
    )
    conn.commit()


def problem_ingest_signoff_pending(conn: sqlite3.Connection,
                                   problem: str) -> bool:
    """True iff `problem` is paused awaiting human ingest sign-off."""
    row = conn.execute(
        "SELECT ingest_signoff_pending FROM problems WHERE name = ?",
        (problem,),
    ).fetchone()
    return bool(row and row["ingest_signoff_pending"])


def goal_by_slug(conn: sqlite3.Connection, problem: str,
                 slug: str) -> sqlite3.Row | None:
    """Resolve a (problem, slug) pair to its goal row (UNIQUE)."""
    return conn.execute(
        "SELECT * FROM goals WHERE problem = ? AND slug = ?",
        (problem, slug),
    ).fetchone()


def set_inject_outcome_detail(conn: sqlite3.Connection, goal_id: int,
                              detail: str, *,
                              outcome: "str | None" = None) -> "int | None":
    """Write `detail` into the `outcome_detail` of the Inject decision
    that produced `goal_id` (single-write invariant → at most one row).
    Used by `asterism reject` so the human's reject reason surfaces to
    the Strategist in `## Completed Inject batches` on its next wake.

    `outcome` additionally SETTLES that decision, and returns its id so
    the caller can fire `maybe_enqueue_inject_batch_done`. The reject
    path needs this since 2026-09-04: it used to settle the inject as a
    side effect of flipping the goal to the hard terminal `dead`, and
    with `dead` retired the node is merely PARKED — a park never settles
    an inject (it is reopenable), so an unsettled batch would suppress
    the very wake the command promises. Guarded on `outcome IS NULL` in
    the same statement, so a second reject of the same node returns None
    instead of re-waking a batch that already reported."""
    if outcome is None:
        conn.execute(
            "UPDATE strategist_decisions SET outcome_detail = ?,"
            " updated_at = ? WHERE produced_goal_id = ?",
            (detail, now(), goal_id),
        )
        conn.commit()
        return None
    row = conn.execute(
        "SELECT id FROM strategist_decisions"
        " WHERE produced_goal_id = ? AND outcome IS NULL",
        (goal_id,),
    ).fetchone()
    conn.execute(
        "UPDATE strategist_decisions SET outcome_detail = ?, outcome = ?,"
        " updated_at = ? WHERE produced_goal_id = ? AND outcome IS NULL",
        (detail, outcome, now(), goal_id),
    )
    conn.commit()
    return int(row["id"]) if row is not None else None


def set_inject_decision_produced_goal(
    conn: sqlite3.Connection, decision_id: int, goal_id: int,
    kind: "str | None" = None,
) -> None:
    """Link an Inject decision row to the Forward goal it produced.
    The decision's `outcome` stays NULL until the goal reaches a
    terminal status — see `propagate_inject_outcome_from_goal`.

    `kind` (v32, #3 attribution): HOW the artifact came to be —
    'minted' | 'alias' | 'reuse' | 'redispatch' | 'disproof'. The
    batch-outcomes render reads it instead of guessing from joins.

    Single-write invariant: a given Strategist decision row produces
    AT MOST one artifact (one goal OR one strategy, not both). If
    either column is already populated, we are about to write a
    second produced-artifact onto the same audit row — the symptom
    of a double dispatch (e.g. residue_thm 2026-05-21: recovery
    hardcoded-Forward re-enqueued an Inject(Backward) as Forward, so
    decision #128 ended up with produced_strategy_id=s10559 from the
    Backward path AND produced_goal_id=g2494 from the Forward
    misroute). Reject the write and log; the decision's first
    produced artifact stays canonical for outcome propagation.
    """
    existing = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id"
        " FROM strategist_decisions WHERE id = ?",
        (decision_id,),
    ).fetchone()
    if existing is None:
        return
    if existing["produced_goal_id"] is not None:
        if int(existing["produced_goal_id"]) == int(goal_id):
            return  # idempotent re-write — same goal, no-op
        print(f"[db] refusing to overwrite produced_goal_id on decision "
              f"{decision_id}: existing={existing['produced_goal_id']}, "
              f"attempted={goal_id}", flush=True)
        return
    if existing["produced_strategy_id"] is not None:
        # Backward Inject dual-set is legitimate: the decision row
        # already has produced_goal_id=target written at INSERT
        # (`_commit_inject_redispatch`), and the worker later sets
        # produced_strategy_id on a strategy whose goal_id == target.
        # Only refuse when the strategy points at a DIFFERENT goal —
        # the residue_thm misroute symptom this guard exists for.
        strat = conn.execute(
            "SELECT goal_id FROM strategies WHERE id = ?",
            (int(existing["produced_strategy_id"]),),
        ).fetchone()
        if strat is None or int(strat["goal_id"]) != int(goal_id):
            print(f"[db] refusing to set produced_goal_id={goal_id} on "
                  f"decision {decision_id}: produced_strategy_id="
                  f"{existing['produced_strategy_id']} already set "
                  f"(double-dispatch indicator)", flush=True)
            return
    if kind is not None:
        conn.execute(
            "UPDATE strategist_decisions SET produced_goal_id = ?,"
            " produced_kind = ?, updated_at = ? WHERE id = ?",
            (goal_id, kind, now(), decision_id),
        )
    else:
        conn.execute(
            "UPDATE strategist_decisions SET produced_goal_id = ?,"
            " updated_at = ? WHERE id = ?",
            (goal_id, now(), decision_id),
        )
    conn.commit()


def set_inject_decision_outcome_detail(
    conn: sqlite3.Connection, decision_id: int, detail: str | None,
) -> None:
    """Stash a pipeline's rich terminal detail (e.g. a Forward decline's
    `## Why` reasoning) on its Inject decision row's `outcome_detail`
    column, so the Strategist's next wake sees WHY the brief was declined
    (#4) — not just the coarse `outcome` enum.

    Only writes while `outcome` is still NULL (pre-cascade): a real
    settled outcome must not be disturbed. `cascade_one`'s later outcome
    write preserves this value via COALESCE. No-op on empty detail."""
    if not detail:
        return
    conn.execute(
        "UPDATE strategist_decisions SET outcome_detail = ?, updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (detail, now(), decision_id),
    )
    conn.commit()


def propagate_inject_outcome_from_goal(
    conn: sqlite3.Connection, goal_id: int,
) -> int | None:
    """When `goal_id` reaches a terminal status, fill the outcome of
    the Inject decision row whose `produced_goal_id` points at it
    (if any, and if its outcome is still NULL).

    Mapping: goal status='proved' → outcome='success'. disproved /
    dead → outcome='failed:<status>'. Other statuses are not terminal
    and this function is a no-op for them — IN PARTICULAR `shelved`,
    which is a reopenable / parked soft-terminal: a shelved goal is NOT
    a completed inject, so its outcome stays NULL (the stall predicate's
    active-check, not a settled outcome, governs whether it suppresses
    T4). Treating shelved as settling here re-fired `inject_batch_done`
    every park (P13 4284 futile spin, 2026-06-15).

    Returns the affected decision row id (caller may then fire
    `_maybe_enqueue_inject_batch_done`), or None if nothing was
    propagated.

    Idempotent: re-running on an already-propagated goal does
    nothing (the `outcome IS NULL` guard).
    """
    row = conn.execute(
        "SELECT id FROM strategist_decisions"
        " WHERE produced_goal_id = ? AND outcome IS NULL",
        (goal_id,),
    ).fetchone()
    if row is None:
        return None
    g = conn.execute(
        "SELECT status FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()
    if g is None:
        return None
    from .. import transitions
    status = str(g["status"])
    if status == "proved":
        outcome = "success"
    elif status in transitions.GOAL_FAILED_TERMINALS:
        outcome = f"failed:{status}"
    else:
        return None  # not terminal (incl. shelved — reopenable); wait
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, updated_at = ?"
        " WHERE id = ? AND outcome IS NULL",
        (outcome, now(), int(row["id"])),
    )
    conn.commit()
    return int(row["id"])


def set_inject_decision_produced_strategy(
    conn: sqlite3.Connection, decision_id: int, strategy_id: int,
) -> None:
    """Link an Inject(Backward/Builder) decision row to the strategy
    its dispatched worker just created. The decision's `outcome`
    stays NULL until the strategy reaches a terminal status — see
    `propagate_inject_outcome_from_strategy`.

    Single-write invariant — see `set_inject_decision_produced_goal`
    for the failure mode this guards against.
    """
    existing = conn.execute(
        "SELECT produced_goal_id, produced_strategy_id"
        " FROM strategist_decisions WHERE id = ?",
        (decision_id,),
    ).fetchone()
    if existing is None:
        return
    if existing["produced_strategy_id"] is not None:
        if int(existing["produced_strategy_id"]) == int(strategy_id):
            return  # idempotent re-write
        print(f"[db] refusing to overwrite produced_strategy_id on "
              f"decision {decision_id}: existing="
              f"{existing['produced_strategy_id']}, "
              f"attempted={strategy_id}", flush=True)
        return
    if existing["produced_goal_id"] is not None:
        # Backward Inject dual-set is legitimate: the decision row's
        # produced_goal_id was written at INSERT (via
        # `_commit_inject_redispatch`) and equals target_id; the
        # worker's just-reserved strategy lives on that same goal.
        # Refuse only when the strategy is on a DIFFERENT goal — the
        # residue_thm 2026-05-21 misroute symptom this guard exists for.
        strat = conn.execute(
            "SELECT goal_id FROM strategies WHERE id = ?",
            (int(strategy_id),),
        ).fetchone()
        if strat is None or int(strat["goal_id"]) != int(existing["produced_goal_id"]):
            print(f"[db] refusing to set produced_strategy_id={strategy_id} "
                  f"on decision {decision_id}: produced_goal_id="
                  f"{existing['produced_goal_id']} already set "
                  f"(double-dispatch indicator)", flush=True)
            return
    conn.execute(
        "UPDATE strategist_decisions SET produced_strategy_id = ?,"
        " updated_at = ? WHERE id = ?",
        (strategy_id, now(), decision_id),
    )
    conn.commit()


def _strategy_death_detail(conn: sqlite3.Connection,
                           strategy_id: int) -> str:
    """One-line WHY for a dead/stalled strategy, destined for the
    producing Inject decision's `outcome_detail` (the strategist's
    always-on batch-outcome surface). Forward declines push their
    `## Why` prose through this column; Backward/Builder redispatches
    historically surfaced a bare enum while the forensics sat in
    `dead_attempts` behind the gated pending_review trigger (07-18
    survey). Derivation: the freshest dead_attempts rows on the
    strategy's own goal (decline shapes — circularity / no_progress
    target the decomposed goal) or its subgoals (cascade shapes — a
    subgoal died/shelved)."""
    s = conn.execute(
        "SELECT goal_id FROM strategies WHERE id = ?",
        (strategy_id,)).fetchone()
    if s is None:
        return ""
    ids = [int(s["goal_id"])] + [int(r["subgoal_id"]) for r in conn.execute(
        "SELECT subgoal_id FROM strategy_subgoals WHERE strategy_id = ?",
        (strategy_id,))]
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT da.failure_reason, da.failure_detail, g.slug"
        f" FROM dead_attempts da JOIN goals g ON g.id = da.target_id"
        f" WHERE da.target_kind = 'Goal' AND da.target_id IN ({marks})"
        f" ORDER BY da.id DESC LIMIT 2",
        ids).fetchall()
    parts = []
    for r in rows:
        d = " ".join((r["failure_detail"] or "").split())
        parts.append(f"`{r['slug']}`: {r['failure_reason']}"
                     + (f" — {d[:300]}" if d else ""))
    return "; ".join(parts)[:700]


def propagate_inject_outcome_from_strategy(
    conn: sqlite3.Connection, strategy_id: int,
) -> int | None:
    """When `strategy_id` reaches a terminal status, fill the outcome
    of the Inject(Backward/Builder) decision row whose
    `produced_strategy_id` points at it (if any, and if outcome is
    still NULL).

    Mapping: strategy 'succeeded' → 'success'. 'superseded' → 'success'
    (the goal got proved by a sibling — Strategist's intent of "make
    this goal terminal-proved" was met, even though by a different
    decomposition). 'dead' → 'failed:dead' (the STRATEGY's own status —
    strategies keep `dead`). 'stalled' → 'failed:stalled'
    (subgoals all settled, >=1 soft-shelved — parked but reopenable).
    Other statuses are not terminal and this function is a no-op.

    Returns the affected decision row id (caller may then fire
    `_maybe_enqueue_inject_batch_done`), or None if nothing was
    propagated.

    Idempotent: re-running on an already-propagated strategy is a
    no-op via the `outcome IS NULL` guard.
    """
    row = conn.execute(
        "SELECT id FROM strategist_decisions"
        " WHERE produced_strategy_id = ? AND outcome IS NULL",
        (strategy_id,),
    ).fetchone()
    if row is None:
        return None
    s = conn.execute(
        "SELECT status FROM strategies WHERE id = ?", (strategy_id,)
    ).fetchone()
    if s is None:
        return None
    status = str(s["status"])
    if status == "succeeded":
        outcome = "success"
    elif status == "superseded":
        # #3(a): the briefed decomposition did NOT run to completion —
        # the target settled via ANOTHER route. Mapping this to
        # 'success' taught the strategist its plan worked; the render
        # spells out the distinction.
        outcome = "superseded"
    elif status == "dead":
        outcome = "failed:dead"
    elif status == "stalled":
        outcome = "failed:stalled"
    else:
        return None  # not terminal; wait
    # Failed redispatches carry their WHY to the strategist's next wake
    # (the `why:` line the Forward decline path already renders) instead
    # of a bare enum. COALESCE: never clobber a detail someone else set.
    detail: str | None = None
    if outcome in ("failed:dead", "failed:stalled"):
        detail = _strategy_death_detail(conn, strategy_id) or None
    conn.execute(
        "UPDATE strategist_decisions SET outcome = ?, updated_at = ?,"
        "       outcome_detail = COALESCE(outcome_detail, ?)"
        " WHERE id = ? AND outcome IS NULL",
        (outcome, now(), detail, int(row["id"])),
    )
    conn.commit()
    return int(row["id"])


