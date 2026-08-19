"""state.groups — the discussion-group store (v35).

SoT: `docs/internal/discussion_group_design.md`.

A **group** is one charter, one Programme, one strategist/adversary loop,
and the subtree it grows. Groups form a tree INSIDE one problem — a parent
must cite its child's bricks and cross-problem citation is forbidden
(`pipeline/_cite_gate.py`), so a group is a partition of a problem, never a
recursive problem.

The invariant the whole design rests on (v40 made it literal): every
group — the top one included — is one charter, judged against that
charter and nothing else. A sub-group does not know it is a sub-group.
It knows it was handed a claim and has to settle it. That is what lets
it reuse every problem-level mechanism unchanged, all the way to
Ingest.

Consequences worth stating up front:

  * The **top group** of each problem is a real row (`parent_group_id IS
    NULL`), not a special case in the code. Its charter is the problem's
    GOAL as the user authored it (written at init; amended only through
    `state/intent.set_charter`). A partial unique index pins "one top
    group per problem".
  * A group's anchor goal is **optional**. The main shape — a burden the
    Strategist delegates while writing its `## Proof` — has none: the group
    starts from prose and mints its own bricks, exactly like a pure-NL
    problem. Only the rescue shape (an existing goal promoted to a group)
    carries an anchor.
  * `set_status` is the single sanctioned mutator, mirroring the discipline
    `state.transitions` enforces for goals / strategies / problems.
"""
from __future__ import annotations

import json as _json
import re
import sqlite3
from typing import Optional

from .db import now

#: A group is alive iff 'active'. The other three are terminal for the
#: parent's purposes: the delegated burden stopped being in flight.
ACTIVE = "active"
TERMINAL_STATUSES = ("delivered", "returned", "closed")
STATUSES = (ACTIVE,) + TERMINAL_STATUSES


# ---------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------

def get(conn: sqlite3.Connection, group_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM groups WHERE id = ?", (int(group_id),)).fetchone()


def top_group(conn: sqlite3.Connection,
              problem: str) -> Optional[sqlite3.Row]:
    """The problem's human-facing group, or None before `ensure_top_group`."""
    return conn.execute(
        "SELECT * FROM groups WHERE problem = ? AND parent_group_id IS NULL",
        (problem,)).fetchone()


def is_top(row: Optional[sqlite3.Row]) -> bool:
    """True iff this group faces a human rather than a parent group.

    The predicate `ReturnToParent` is gated on: a group with no parent has
    nowhere to hand its charter back to, which is what keeps the
    difficulty escape hatch structurally away from the human channel
    (`RequestUserAmend` stays what it always was — for a wrong user file).
    """
    return row is not None and row["parent_group_id"] is None


def children(conn: sqlite3.Connection, group_id: int, *,
             active_only: bool = False) -> list[sqlite3.Row]:
    sql = "SELECT * FROM groups WHERE parent_group_id = ?"
    if active_only:
        sql += " AND status = 'active'"
    return list(conn.execute(sql + " ORDER BY id", (int(group_id),)))


#: Hard depth cap on the group tree (owner ruling 2026-08-19): the top
#: group and its direct sub-groups may Delegate; a depth-2 group may
#: not. Group depth partitions JUDGMENT, not mathematics — the goal
#: tree under any group stays unbounded — and past depth 2 the observed
#: behavior was pipeline-stage delegation under stacked hypotheses
#: (d7→d10 in 4.5h, six single-task charters, all from zero-own-brick
#: groups, 2026-08-18) with no strategist left holding the whole
#: argument. Mechanical: enforced on ancestry count at verify, never on
#: charter text.
GROUP_DEPTH_CAP = 2


def depth(conn: sqlite3.Connection, group_id: int) -> int:
    """0 for the top group, 1 for its children, … (ancestry count)."""
    return len(ancestors(conn, int(group_id)))


def ancestors(conn: sqlite3.Connection, group_id: int) -> list[sqlite3.Row]:
    """From the parent up to the top group, nearest first. Cycle-safe."""
    out: list[sqlite3.Row] = []
    seen: set[int] = {int(group_id)}
    row = get(conn, group_id)
    while row is not None and row["parent_group_id"] is not None:
        nxt = int(row["parent_group_id"])
        if nxt in seen:
            break               # a cycle is a framework bug; do not spin
        seen.add(nxt)
        row = get(conn, nxt)
        if row is None:
            break
        out.append(row)
    return out


#: Nearest OWNERSHIP MARK at-or-above `?`. Same upward walk as
#: `programme.rev_for_goal` — the goal tree has no parent column, an edge
#: is `strategies.goal_id → strategy_subgoals → subgoal_id`
#: (`idx_ssg_subgoal` covers the step).
#:
#: Two kinds of mark, and BOTH must be looked for at every level, not
#: only at depth 0: a goal is a mark if some group anchors it, or if some
#: decision produced it. Checking anchors only on the goal itself left a
#: rescue-shape group's OWN subtree resolving to the top group — i.e. a
#: review on the work that group is doing would have woken somebody else.
#: At equal depth an anchor outranks a decision, because that is exactly
#: the rescue shape: the parent's decision promoted the goal, the child
#: owns it.
_OWNING_GROUP_SQL = """
WITH RECURSIVE up(gid, depth) AS (
  VALUES(?, 0)
  UNION
  SELECT s.goal_id, up.depth + 1
    FROM strategy_subgoals ss
    JOIN strategies s ON s.id = ss.strategy_id
    JOIN up ON ss.subgoal_id = up.gid
)
SELECT gid, depth, rank, did FROM (
  SELECT gr.id AS gid, up.depth AS depth, 0 AS rank, 0 AS did
    FROM up JOIN groups gr ON gr.anchor_goal_id = up.gid
  UNION ALL
  SELECT d.group_id AS gid, up.depth AS depth, 1 AS rank, d.id AS did
    FROM up JOIN strategist_decisions d
      ON CAST(d.produced_goal_id AS INTEGER) = up.gid
   WHERE d.group_id IS NOT NULL
)
 ORDER BY depth ASC, rank ASC, did DESC
 LIMIT 1
"""


def group_for_goal(conn: sqlite3.Connection, problem: str,
                   goal_id: int) -> Optional[sqlite3.Row]:
    """Which group owns this goal — i.e. whose Strategist a review on it
    should wake.

    DERIVED, not stored. There is no `goals.group_id` column for the same
    reason there is no `goals.parent_id`: every goal-creation path would
    have to remember to set it (Forward mint, Backward sub-goals, dedupe
    reuse, alias, the disproof mint, revival), and a column that one path
    forgets is worse than an answer computed from the edges that already
    exist. This is also what retired `goals.entry_kind` in v33.

    Resolution, most specific first:

      1. the goal IS a group's anchor → that group (the rescue shape: the
         anchor belongs to the CHILD, while the decision that promoted it
         belongs to the parent, so this case must come first);
      2. the nearest goal at-or-above it that a decision produced → that
         decision's authoring group. This covers more than it looks:
           * a mint / reuse / alias / disproof goal resolves at depth 0,
             because the producing decision names it in
             `produced_goal_id`;
           * a worker's sub-goals have no decision of their own and
             inherit from the goal above them;
           * `detached` does NOT break the walk — that flag only seeds the
             top-down alive CTE (`root ∪ detached`); the
             `strategy_subgoals` edges this walk climbs are untouched, so
             a detached mint's whole subtree still resolves;
           * when two groups have both dispatched the same goal (a reuse
             repoint), the LATEST decision wins — the group most recently
             waiting on it is the one a review concerns.
      3. the top group — the root goal, orphans, and pre-group work.
         Never None once the problem is initialised.

    Finally: a resolved group that is no longer `active` is replaced by
    its nearest active ancestor. A finished group has no seat, so waking
    it would drop the event on the floor — and its subtree's leftovers are
    exactly what the parent needs to see.
    """
    row = None
    hit = conn.execute(_OWNING_GROUP_SQL, (int(goal_id),)).fetchone()
    if hit is not None and hit["gid"] is not None:
        row = get(conn, int(hit["gid"]))
    if row is None:
        return top_group(conn, problem)
    return _nearest_active(conn, problem, row)


def goals_by_group(conn: sqlite3.Connection,
                   problem: str) -> "dict[int, int]":
    """`{goal_id: owning group_id}` for the whole problem, in one pass.

    The bulk twin of `group_for_goal`, and it must agree with it goal for
    goal — two predicates disagreeing about one node is the disease this
    codebase has paid for three times (P13's 4284-spin → the cond-4
    deadlock → the b6 wake pump). `test_group_ownership_agrees_in_bulk`
    pins the agreement; change one and that test tells you.

    Why a bulk form exists at all: the per-goal walk is a recursive CTE,
    and the stall predicate needs the whole set on every dispatcher tick.
    On a 588-goal problem that is one pass instead of 588.

    Resolution mirrors the single-goal version: anchors first, then the
    nearest ancestor with a producing decision (multi-source BFS gives
    exactly "nearest"), then the top group, then the not-active
    substitution.
    """
    top = top_group(conn, problem)
    if top is None:
        return {}
    top_id = int(top["id"])

    owner: "dict[int, int]" = {}
    # Producing decisions, oldest first so the LATEST claimant wins —
    # the same tie-break `group_for_goal` applies (`d.id DESC`).
    for r in conn.execute(
        "SELECT d.produced_goal_id AS gid, d.group_id AS grp"
        "  FROM strategist_decisions d"
        " WHERE d.problem = ? AND d.produced_goal_id IS NOT NULL"
        "   AND d.group_id IS NOT NULL ORDER BY d.id ASC", (problem,)
    ):
        owner[int(r["gid"])] = int(r["grp"])
    # Anchors outrank producing decisions (the rescue shape: the anchor
    # belongs to the CHILD, the decision that promoted it to the parent).
    for r in conn.execute(
        "SELECT id, anchor_goal_id FROM groups"
        " WHERE problem = ? AND anchor_goal_id IS NOT NULL", (problem,)
    ):
        owner[int(r["anchor_goal_id"])] = int(r["id"])

    children: "dict[int, list[int]]" = {}
    for r in conn.execute(
        "SELECT s.goal_id AS par, ss.subgoal_id AS kid"
        "  FROM strategy_subgoals ss"
        "  JOIN strategies s ON s.id = ss.strategy_id"
        "  JOIN goals g ON g.id = s.goal_id"
        " WHERE g.problem = ?", (problem,)
    ):
        children.setdefault(int(r["par"]), []).append(int(r["kid"]))

    # Multi-source BFS from every explicitly-owned goal: a node reached
    # at distance d belongs to the closest owner above it, which is what
    # the upward walk's `ORDER BY depth ASC` says.
    frontier = list(owner.items())
    while frontier:
        nxt: "list[tuple[int, int]]" = []
        for gid, grp in frontier:
            for kid in children.get(gid, ()):
                if kid not in owner:
                    owner[kid] = grp
                    nxt.append((kid, grp))
        frontier = nxt

    status = {int(r["id"]): str(r["status"]) for r in conn.execute(
        "SELECT id, status FROM groups WHERE problem = ?", (problem,))}
    parent = {int(r["id"]): r["parent_group_id"] for r in conn.execute(
        "SELECT id, parent_group_id FROM groups WHERE problem = ?",
        (problem,))}

    def _active(gid: int) -> int:
        seen = set()
        cur: "int | None" = gid
        while cur is not None and cur not in seen:
            if status.get(cur) == ACTIVE:
                return cur
            seen.add(cur)
            cur = parent.get(cur)
        return top_id

    out: "dict[int, int]" = {}
    for r in conn.execute("SELECT id FROM goals WHERE problem = ?",
                          (problem,)):
        gid = int(r["id"])
        out[gid] = _active(owner.get(gid, top_id))
    return out


def goal_ids_in_group(conn: sqlite3.Connection, problem: str,
                      group_id: int) -> "set[int]":
    """The goals this group answers for — its slice of the tree."""
    return {g for g, grp in goals_by_group(conn, problem).items()
            if grp == int(group_id)}


def _nearest_active(conn: sqlite3.Connection, problem: str,
                    row: sqlite3.Row) -> Optional[sqlite3.Row]:
    """`row` if it is still working, else the closest ancestor that is —
    falling back to the top group, which never terminates while the
    problem is live."""
    if str(row["status"]) == ACTIVE:
        return row
    for anc in ancestors(conn, int(row["id"])):
        if str(anc["status"]) == ACTIVE:
            return anc
    return top_group(conn, problem)


# ---------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------

def ensure_top_group(conn: sqlite3.Connection, problem: str, *,
                     charter: str = "") -> int:
    """Create the problem's top group if it has none. Returns its id.

    Idempotent, and cheap enough to call on any path that might be the
    first to touch a problem — a problem without a top group has no seat
    for its Strategist at all, so failing closed here would be silent.

    `charter` is the problem's goal, passed by init on first creation;
    an existing top group's charter is never touched here (that write
    belongs to `state/intent.set_charter`, which records history).
    """
    row = top_group(conn, problem)
    if row is not None:
        return int(row["id"])
    ts = now()
    clocks = conn.execute(
        "SELECT last_routine_at, last_strategist_at FROM problems"
        " WHERE name = ?", (problem,)).fetchone()
    cur = conn.execute(
        "INSERT INTO groups (problem, parent_group_id, charter, status,"
        " last_routine_at, last_strategist_at, created_at, updated_at)"
        " VALUES (?, NULL, ?, 'active', ?, ?, ?, ?)",
        (problem, str(charter).strip(),
         clocks["last_routine_at"] if clocks else None,
         clocks["last_strategist_at"] if clocks else None, ts, ts))
    return int(cur.lastrowid)


def open_group(conn: sqlite3.Connection, *, problem: str,
               parent_group_id: int, charter: str,
               anchor_goal_id: "int | None" = None,
               opened_by: "int | None" = None,
               conventions_seed: str = "") -> int:
    """Open a sub-group under `parent_group_id`. Returns its id.

    `charter` is the parent's `Delegate` brief verbatim — the claim this
    group exists to settle, and the fixed reference point its own Adversary
    judges against.

    `conventions_seed` is the parent's `## Conventions` copied at this
    moment. Workers read conventions from their own group only, so
    without the copy a footgun learned above this group would never
    reach it — and a group cannot ask for a rule it does not know
    exists. The copy is read until this group ships its own section;
    what to keep is then the group's own call.
    """
    if not str(charter).strip():
        raise ValueError("a group's charter must not be empty")
    ts = now()
    cur = conn.execute(
        "INSERT INTO groups (problem, parent_group_id, charter,"
        " anchor_goal_id, opened_by, status, conventions_seed,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?)",
        (problem, int(parent_group_id), str(charter).strip(),
         int(anchor_goal_id) if anchor_goal_id is not None else None,
         int(opened_by) if opened_by is not None else None,
         str(conventions_seed or "").strip(), ts, ts))
    return int(cur.lastrowid)


def set_status(conn: sqlite3.Connection, group_id: int,
               status: str, *, event: str = "") -> None:
    """The single sanctioned status mutator, and the group FSM's chokepoint.

    Reaching a terminal status is what fills the opening `Delegate` row's
    outcome, which in turn completes the parent's batch and wakes it — the
    same real-completion semantics a produced goal or strategy carries.
    Driving that write anywhere else would strand the parent.

    The edge is validated against `transitions.GROUP_EDGES` (v35 follow-up).
    Goals, strategies and problems have had declared edge tables since the
    incidents that motivated them; groups shipped with an enum and this
    chokepoint but no law, so nothing said a terminal group may not be
    resurrected or terminated twice — and a group's terminal write has a
    SIDE EFFECT the other entities' do not, waking the parent. The check
    lives here rather than in a separate `apply_group_transition` because
    this function is already the one door, and a second entry point is
    exactly what the other three had to grow lints to prevent.
    """
    if status not in STATUSES:
        raise ValueError(
            f"unknown group status {status!r}; expected one of {STATUSES}")
    from . import transitions as _t
    row = conn.execute(
        "SELECT status, anchor_goal_id FROM groups WHERE id = ?",
        (int(group_id),)).fetchone()
    frm = str(row["status"]) if row is not None else None
    _t._check("group", frm, status, _t.GROUP_EDGES, event)
    conn.execute(
        "UPDATE groups SET status = ?, updated_at = ? WHERE id = ?",
        (status, now(), int(group_id)))
    if status == "closed" and row is not None:
        # A closed rescue-shape group parks its anchor goal — HERE, so
        # the direct `CloseGroup`, the ancestor cascade below and the
        # startup orphan sweep all do it, not just the first. `closed`
        # only: `delivered` / `returned` hand their anchor's fate to the
        # parent's next batch, which is #217's open question.
        _t.park_group_anchor(conn, row["anchor_goal_id"])
    if status in TERMINAL_STATUSES:
        # A RETIRED CHARTER RETIRES THE WORK IT DELEGATED. Goals have
        # cascaded downward since the beginning (`transitions.
        # _cascade_shelve_descendants`); groups never did, and
        # `_commit_close_group` retired exactly one level. So a
        # grandchild kept working a charter its grandparent had already
        # withdrawn, and nothing anywhere told it. Measured on
        # union_closed 2026-08-16: group 420 closed 425 at 02:12Z
        # because the certificate it wanted "is now kernel-proved by the
        # independent s24581 route"; 425's child 427 never heard, and at
        # 05:02Z opened five sub-projects to binary-split a 2^21 mask
        # space, which opened their own. Twenty-two of the next
        # thirty-eight bricks served the withdrawn charter.
        #
        # Descendants become `closed` whatever verb retired the
        # ancestor: they did not deliver and they did not hand back —
        # the parent's charter went away under them, which is what
        # `closed` means. Same shape as the goal cascade: frontier walk,
        # already-terminal skipped, idempotent, and each child goes
        # through this same door so its `Delegate` row still settles.
        for kid in children(conn, int(group_id)):
            if str(kid["status"]) == ACTIVE:
                set_status(conn, int(kid["id"]), "closed",
                           event="ancestor_retired")
        from . import db as _db
        filled = _db.propagate_inject_outcome_from_group(conn, int(group_id))
        if filled is not None:
            _db.maybe_enqueue_inject_batch_done(conn, filled)
        # A parent with live children is WAITING and its routine clock
        # is frozen (`groups_needing_t1` skips it). Restart the cadence
        # here — the freeze's release point — so the waiting hours never
        # read as overdue: without this, a 7-hour delegation would fire
        # a routine the instant the last child settles, right on top of
        # the batch-done relay wake that settling already enqueues.
        parent_row = conn.execute(
            "SELECT parent_group_id FROM groups WHERE id = ?",
            (int(group_id),)).fetchone()
        if parent_row is not None and parent_row["parent_group_id"] is not None:
            conn.execute(
                "UPDATE groups SET last_routine_at = ? WHERE id = ?",
                (now(), int(parent_row["parent_group_id"])))


def touch_strategist(conn: sqlite3.Connection, group_id: int, *,
                     routine: bool) -> None:
    """Advance this group's wake clocks after a committed batch.

    Mirrors `db.update_problem_last_strategist_at` /
    `update_problem_last_routine_at`, which stay authoritative until the
    per-group seat lands (Stage D). While both exist they are written
    together — a divergence between them is a bug, not a fallback.
    """
    ts = now()
    if routine:
        conn.execute(
            "UPDATE groups SET last_strategist_at = ?, last_routine_at = ?,"
            " updated_at = ? WHERE id = ?", (ts, ts, ts, int(group_id)))
    else:
        conn.execute(
            "UPDATE groups SET last_strategist_at = ?, updated_at = ?"
            " WHERE id = ?", (ts, ts, int(group_id)))


def _qualify_headings(charter: str, gid: int) -> str:
    """Stamp `[group N]` into every markdown heading of a STACKED
    charter, so identical headings from different charters stay
    addressable. Charters are agent prose sharing a template — two
    charters in one `charter.md` both said `## The claim to settle`
    (measured 2026-08-15), and a section ask can only name one of
    them. This group's OWN charter keeps its headings verbatim; only
    the stacked context is stamped. Fence-aware: a `#` inside a code
    block is code, not structure."""
    out: "list[str]" = []
    fenced = False
    for line in charter.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        m = None if fenced else re.match(r"^(#{1,4})\s+(\S.*)$", line)
        out.append(f"{m.group(1)} [group {gid}] {m.group(2)}" if m
                   else line)
    return "\n".join(out)


_DELEGATION_PROSE_RE = re.compile(
    r"^##\s+(why a project|inheritance)\b", re.IGNORECASE)


def _charter_claim(charter: str) -> str:
    """The charter minus its delegation prose (`## Why a project` /
    `## Inheritance`) — what a STACKED entry carries.

    Criterion 3 judges whether MY claim leans on an ancestor's CLAIM;
    the two dropped sections justify a delegation, not a judgement.
    Sections are dropped by NAME, not position — a charter's claim may
    itself sit under a `## The claim to settle` heading, so "cut at the
    first ##" would cut the claim. Measured 2026-08-18 on a depth-10
    chain: full stacking made charter.md 37.4KB against a 1.5KB own
    charter, the second-largest inspect-truncation source of the slice
    (130 clipped reads). Fence-aware, like `_qualify_headings`."""
    out: "list[str]" = []
    fenced = False
    dropping = False
    for line in charter.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and re.match(r"^#{1,2}\s", line):
            dropping = bool(_DELEGATION_PROSE_RE.match(line))
        if not dropping:
            out.append(line)
    return "\n".join(out).strip()


def charter_digest(conn: sqlite3.Connection, problem: str,
                    group_id: "int | None") -> str:
    """`charter.md` — what a group is judged against (v35; every depth
    including the top since the v40 Manifest retirement).

    Three parts, all structured data rather than free text:

      1. **this group's charter** — the fixed reference point: does the
         proposal settle THIS claim? For the top group that is the
         problem's goal as the user authored it.
      2. **the ancestor chain** — every charter above it (top group:
         none). Criterion 3 (non-circular) otherwise only catches a
         claim that leans on the PARENT's conclusion, and on a deep
         tree circularity arrives a generation later: C's charter
         being, in substance, grandparent A's.
      3. **charters this subtree already handed back** — with flavour and
         post-mortem. Deliberately NOT a gate: re-attacking a failed line
         is legitimate, and whether this attempt differs is a judgement
         about mathematics, which a string comparison cannot make (the
         same reason the dead-twin gate misfires, task #112). The judge
         gets the material and decides on the `value` criterion.

    `group_id=None` resolves to the top group (problem-level callers).
    """
    if group_id is None:
        top = top_group(conn, problem)
        if top is None:
            return ""
        group_id = int(top["id"])
    me = get(conn, int(group_id))
    if me is None:
        return ""
    out = ["# Charter — what this group was asked to settle", "",
           str(me["charter"]).strip(), ""]
    # Every ancestor, the top group included: its charter is the
    # problem's goal, and a deep chain restating the root claim is the
    # circularity criterion 3 exists to catch (v40).
    above = ancestors(conn, int(group_id))
    if above:
        out += ["## Charters above this one", "",
                "Your charter must not depend on any of these being "
                "true — that is circular, however many generations "
                "apart. Each shows its CLAIM only; the delegation "
                "prose is not this judgement's business.", ""]
        for i, a in enumerate(above, 1):
            out += [f"{i}. (group {a['id']}) "
                    f"{_qualify_headings(_charter_claim(str(a['charter'])), int(a['id']))}",
                    ""]
    # Scope: groups returned to ME or to one of MY ancestors — the
    # failed attempts on this chain, which is what "my parent already
    # tried this line" looks like. NOT problem-wide: a cousin branch's
    # failures are none of this judge's business, and pulling them in
    # would break the per-group projection isolation the design rests
    # on. Strict "my own subtree" would be near-empty (a group just
    # opened has no descendants), and the case that matters is exactly
    # the sibling my parent tried before me.
    chain = [int(group_id)] + [int(a["id"]) for a in
                               ancestors(conn, int(group_id))]
    marks = ",".join("?" * len(chain))
    returned = conn.execute(
        "SELECT g.id, g.charter, d.reason, d.payload"
        "  FROM groups g"
        "  LEFT JOIN strategist_decisions d"
        "    ON d.produced_group_id = g.id"
        "   AND d.decision_kind = 'ReturnToParent'"
        f" WHERE g.problem = ? AND g.status = 'returned'"
        f"   AND g.parent_group_id IN ({marks})"
        " ORDER BY g.id", (problem, *chain)).fetchall()
    if returned:
        out += ["## Charters your chain already handed back", "",
                "Context, not a verdict: a line that failed may be worth "
                "re-attacking. Judge whether THIS attempt differs.", ""]
        for r in returned:
            flavour = ""
            try:
                flavour = str(_json.loads(r["payload"] or "{}").get(
                    "flavour") or "")
            except (TypeError, ValueError):
                pass
            out += [f"- (group {r['id']}"
                    + (f", {flavour}" if flavour else "") + ") "
                    + _qualify_headings(_charter_claim(str(r["charter"])),
                                        int(r["id"])),
                    f"  - post-mortem: {str(r['reason'] or '(none)')}"]
        out.append("")
    return "\n".join(out)


