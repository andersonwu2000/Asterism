"""The twin-strategy guard: what to do when a decomposition's whole
contribution is a link set some existing strategy on the same goal
already waits on.

Split out of `backward.py` 2026-09-07, when the guard stopped being a
yes/no and became a three-way verdict (owner ruling after g10929). The
cluster is self-contained — match the twin, judge its wait set,
refuse with the way out, or ADOPT it — and `backward.py` re-exports
every name, so call sites and tests are unchanged.

The history it carries: the P3 guard was added for the b6 strategy
pile (~30 byte-identical reductions s22785-s22831) and it did stop
that. What it could not express is a twin that is RIGHT and STUCK:
s27301 waited on the shelved g10931, so the five decompositions that
would have revived g10931 (52a41d36, 17cad4a8, 2602be07, 68f648e1,
ca70d2dd) were each refused as duplicates of the strategy they were
about to unblock.
"""
from __future__ import annotations

from ..state import transitions
from ._cite_gate import revive_cited_goals


def _existing_duplicate_strategy(conn, goal_id: int,
                                 linked_set: "set[int]") -> "int | None":
    """The id of an existing 'proposed'/'stalled' strategy on `goal_id`
    whose subgoal set equals `linked_set`, or None. P3 duplicate-strategy
    guard: with the statement-defeq reuse link (P1) live, a walled
    re-decomposition resolves to pure links — if an identical link set
    already exists, committing another strategy row is pure pile-up.
    Only live-ish statuses count: a dead/superseded twin does not block
    a fresh assertion of the same structure."""
    if not linked_set:
        return None
    by_sid: "dict[int, set[int]]" = {}
    for r in conn.execute(
        "SELECT s.id AS sid, ss.subgoal_id AS gid FROM strategies s"
        " JOIN strategy_subgoals ss ON ss.strategy_id = s.id"
        " WHERE s.goal_id = ? AND s.status IN ('proposed','stalled')",
        (int(goal_id),),
    ):
        by_sid.setdefault(int(r["sid"]), set()).add(int(r["gid"]))
    for sid in sorted(by_sid):
        if by_sid[sid] == linked_set:
            return sid
    return None


#: Sub-goal statuses from which a waiting strategy can still resume:
#: work is either done (`proved`) or reachable.
_WAIT_SET_LIVE = ("open", "attempting", "pending_strategist_review")


def _wait_set_blockers(conn, strategy_id: int, *,
                       alive_after: "set[int]") -> "list[tuple[int, str, str]]":
    """`(goal_id, slug, status)` for every sub-goal of `strategy_id` that
    stops it from ever resuming — the ones that are neither proved nor
    alive. `alive_after` names goals THIS commit is about to revive, so
    the question asked is "can it resume once this patch lands", not
    "could it resume a moment ago"."""
    out: "list[tuple[int, str, str]]" = []
    for r in conn.execute(
        "SELECT g.id AS gid, g.slug AS slug, g.status AS status"
        " FROM strategy_subgoals ss JOIN goals g ON g.id = ss.subgoal_id"
        " WHERE ss.strategy_id = ? ORDER BY ss.position, g.id",
        (int(strategy_id),),
    ):
        gid, status = int(r["gid"]), str(r["status"])
        if (status == "proved" or status in _WAIT_SET_LIVE
                or gid in alive_after):
            continue
        out.append((gid, str(r["slug"]), status))
    return out


def _duplicate_strategy_verdict(
    conn, goal_id: int, linked_set: "set[int]", *,
    alive_after: "set[int] | None" = None,
) -> "tuple[str, int | None, list[tuple[int, str, str]]]":
    """`(action, twin_sid, blockers)` for a decomposition whose whole
    contribution is the link set `linked_set` — `action` is
    'commit' | 'adopt' | 'refuse'.

    The P3 twin guard used to answer yes/no and, on yes, FAIL the
    pipeline. Owner ruling 2026-09-07 after g10929: liveness is judged
    by REACHABILITY of the twin's wait set, and a live twin is not a
    failure but a thing to JOIN.

      * no twin → 'commit'. Ordinary road.
      * twin whose wait set is all proved-or-alive (counting the goals
        this commit revives) → 'adopt'. The twin says exactly what this
        patch says and it can still get there; the right outcome is to
        resume it, not to burn an attempt telling the agent it wrote a
        duplicate.
      * twin blocked by a goal that is hard-terminal against it
        (`disproved`) → 'commit'. A strategy waiting on a refuted
        statement will never resume, so it blocks nothing; the fresh
        assertion is allowed through.
      * twin blocked by something still parked and NOT revived here
        (a person's park, a goal the patch does not cite) → 'refuse',
        with the blockers named so the message can carry the way out.

    Before this, g10929's five decompositions (52a41d36, 17cad4a8,
    2602be07, 68f648e1, ca70d2dd) were each refused as duplicates of
    s27301 — which was `stalled` on the shelved g10931 and could not
    resume without exactly the revive those decompositions were asking
    for. The guard's yes/no shape could not express that.
    """
    sid = _existing_duplicate_strategy(conn, goal_id, linked_set)
    if sid is None:
        return "commit", None, []
    blockers = _wait_set_blockers(
        conn, sid, alive_after=set(alive_after or ()))
    if not blockers:
        return "adopt", sid, []
    if any(st in transitions.GOAL_FAILED_TERMINALS
           for _, _, st in blockers):
        return "commit", sid, blockers
    return "refuse", sid, blockers


def _duplicate_refusal_detail(sid: int, linked_set: "set[int]",
                              blockers: "list[tuple[int, str, str]]") -> str:
    """The remaining refusal, with the blocking goals, their statuses
    and the way out named (owner ruling 2026-09-07 (c)). The old text
    said only "s<id> is already waiting on those gates. Nothing new
    will happen" — true, and unactionable: it named no goal, no status,
    and no move the agent could make instead."""
    waits = ", ".join(f"g{gid} (`{slug}`, {status})"
                      for gid, slug, status in blockers)
    return (
        f"this decomposition's whole contribution is the link set "
        f"{sorted(linked_set)}, which existing strategy s{sid} on this "
        f"goal already waits on — but s{sid} cannot resume: it waits on "
        f"{waits}. Adding a second strategy with the same links would "
        f"wait on the same thing. Either CITE the blocking goal(s) in "
        f"your patch — citing a parked goal revives it and this "
        f"decomposition is then adopted onto s{sid} — or decompose "
        f"without them, into pieces that do not depend on a parked "
        f"statement."
    )


def _adopt_twin_strategy(conn, *, goal_id: int, twin_sid: int,
                         reserved_sid: int, leading: str,
                         revive_ids: "set[int]"):
    """Land a decomposition that turned out to restate an existing,
    still-reachable strategy: revive what it cites, resume the twin,
    and retire this pipeline's own reserved row.

    NOT a failure (owner ruling 2026-09-07): no attempt is burned, no
    dead_attempts row is written, and the pipeline returns `success` —
    the agent's move was right, it simply coincided with one already on
    the board. The reserved row is `superseded` rather than deleted so
    an Inject that produced it still settles (`superseded` propagates as
    'success' — the decomposition it asked for exists), and it carries
    the agent's annotation so the row explains itself in TREE.md.

    The parent goal's flip to `attempting` is cascade_one's, on the
    `success` outcome: the twin is `proposed` again by then, so its
    has-live-strategy check passes."""
    from . import PipelineResult
    revive_cited_goals(conn, set(revive_ids), citing_goal_id=goal_id)
    row = conn.execute("SELECT status FROM strategies WHERE id = ?",
                       (int(twin_sid),)).fetchone()
    if row is not None and str(row["status"]) == "stalled":
        # Same un-stall the Strategist's redispatch does: a strategy
        # parked because its last live sub-goal settled has to conduct
        # again for the revived goal to be reachable at all.
        transitions.apply_strategy_transition(
            conn, int(twin_sid), "proposed", event="strategist_unstall")
    conn.execute("UPDATE strategies SET proposal_md = ? WHERE id = ?",
                 (leading, int(reserved_sid)))
    transitions.apply_strategy_transition(
        conn, int(reserved_sid), "superseded", event="sibling_won")
    conn.commit()
    detail = f"matches s{twin_sid}, which resumes"
    print(f"[backward-adopt] g{goal_id}: decomposition {detail} "
          f"(s{reserved_sid} superseded)", flush=True)
    return PipelineResult(outcome="success", failure_detail=detail,
                          proposal_md=leading)
