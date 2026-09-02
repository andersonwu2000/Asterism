"""state.commands — the human command queue (human_interface_design.md
§3.3).

Two halves, deliberately in different processes:

  * serve INSERTs a row (`enqueue`) and hands back the id as a receipt.
    A write endpoint must never reach into the engine's state — the
    queue IS the boundary, and it is what makes a command idempotent
    (the key), optimistically concurrent (`expected_revision`) and
    answerable later (`GET /api/commands/{id}`).
  * the daemon applies queued rows once per tick (`apply_pending`)
    through the SAME appliers the Strategist's own decisions go through
    (`pipeline/strategist/commit.py`), so a person's command has the
    machine's side effects, the machine's batch bookkeeping and the
    machine's audit row — with `actor='human'`, the semantic field
    §3.2's predicates read.

What the human path does NOT go through is the Strategist's verifier
(`pipeline/strategist/verify.py`). That gate encodes the MACHINE's
obligations — a `ConfirmShelve` must be paired with an `Inject`
(`verify.verify_decisions`, the "the framework never stops itself"
rule), a `Delegate` must justify why the group cannot prove it itself —
and a person is exactly the actor those obligations do not bind (§1.3,
owner ruling 2026-09-02: "人是唯一被允許喊停的角色"). The requirements a
person DOES owe are §1.3's own, and they are checked here.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import db

#: `human_commands.kind` CHECK (v48). One spelling; `enqueue` refuses
#: anything else before the DB has to.
KINDS: frozenset[str] = frozenset({
    "Delegate", "ReturnToParent", "MarkDeliverable",
    "ConfirmShelve", "FetchPaper", "Inject"})

#: Stamped into `outcome` immediately BEFORE the appliers run. They
#: commit as they go (each `_commit_*` helper calls `conn.commit()`), so
#: the row cannot be marked in the same transaction as its effects: a
#: crash between the two would leave a queued row whose decision already
#: landed, and the next tick would apply it AGAIN — two spawns for one
#: Inject, a re-park for one ConfirmShelve. A queued row that already
#: carries the stamp is therefore crash residue, and is refused.
ATTEMPT_MARK = "applying"

#: `FetchPaper` is in §3.3's CHECK list, but the Scholar pipeline it
#: named was retired 2026-08-22 (`020ebf85`, owner ruling): there is no
#: applier for the kind and no worker to receive it. Refusing loudly is
#: the honest answer — an "applied" row that dispatched nothing would be
#: the worse failure (CLAUDE.md: never patch around a missing mechanism).
_FETCHPAPER_REFUSAL = (
    "FetchPaper is retired (2026-08-22): the Scholar pipeline it "
    "dispatched no longer exists, so nothing would fetch this. Papers "
    "now arrive through the Strategist's own tools during its wake "
    "(`paper_search` / `paper_fetch`), or by shelving the pdf into the "
    "problem's papers yourself.")


# ---------------------------------------------------------------------
# rows
# ---------------------------------------------------------------------

def _row(r: sqlite3.Row) -> dict:
    """One queue row as a plain dict, `payload` already decoded — every
    reader gets the parsed object so nobody re-implements the decode."""
    try:
        payload = json.loads(r["payload"] or "{}")
    except (TypeError, ValueError):
        payload = {}
    return {
        "id": int(r["id"]),
        "problem": str(r["problem"]),
        "kind": str(r["kind"]),
        "payload": payload if isinstance(payload, dict) else {},
        "idempotency_key": str(r["idempotency_key"]),
        "expected_revision": (None if r["expected_revision"] is None
                              else int(r["expected_revision"])),
        "status": str(r["status"]),
        "outcome": r["outcome"],
        "decision_id": (None if r["decision_id"] is None
                        else int(r["decision_id"])),
        "created_at": str(r["created_at"]),
        "applied_at": r["applied_at"],
    }


def get(conn: sqlite3.Connection, command_id: int) -> "dict | None":
    r = conn.execute("SELECT * FROM human_commands WHERE id = ?",
                     (int(command_id),)).fetchone()
    return None if r is None else _row(r)


def pending(conn: sqlite3.Connection) -> "list[dict]":
    """Queued rows, oldest first — the order a person issued them in is
    the order they take effect in."""
    return [_row(r) for r in conn.execute(
        "SELECT * FROM human_commands WHERE status = 'queued'"
        " ORDER BY id ASC")]


# ---------------------------------------------------------------------
# the target, and its revision
# ---------------------------------------------------------------------

#: The kinds whose target is a GROUP. Everything else targets a goal.
#: `target_of` reads the id out of the payload by this split, and
#: `revision` counts it in the column that actually holds it.
GROUP_TARGETED: frozenset[str] = frozenset({"ReturnToParent"})


def target_of(kind: str, payload: dict) -> "int | None":
    """The id this command acts on — a goal for the four goal-targeted
    kinds, a group for `ReturnToParent`. None when the command targets
    nothing (a `Delegate` that mints a group from prose, `FetchPaper`).
    """
    if kind in GROUP_TARGETED:
        gid = payload.get("group_id")
    else:
        gid = payload.get("target_goal_id", payload.get("target_id"))
    try:
        return None if gid is None else int(gid)
    except (TypeError, ValueError):
        return None


def revision(conn: sqlite3.Connection, *, kind: str, payload: dict) -> int:
    """The target's revision: how many decisions have been filed against
    it. A change-detector, not a version vector — the front-end reads it
    (through `preview`), shows the person a state, and sends it back with
    the command; a decision landing in between means the person acted on
    a page that has moved.

    Counted in the column that HOLDS the id (§3.3 ruling 2026-09-02).
    `strategist_decisions.target_id` is a goal id and `group_id` is a
    group id; the two id spaces are independent and both start at 1, so
    counting a group by bare `target_id` counts the decisions of an
    unrelated GOAL that happens to carry the same number. That is not a
    safe over-count: it is a `stale` refusal against a state nothing
    moved, on the one command a person issues to stop work — and no
    retry clears it, because the number never goes back down.
    """
    tid = target_of(kind, payload)
    if tid is None:
        return 0
    column = "group_id" if kind in GROUP_TARGETED else "target_id"
    return int(conn.execute(
        f"SELECT COUNT(*) FROM strategist_decisions WHERE {column} = ?",
        (tid,)).fetchone()[0])


# ---------------------------------------------------------------------
# what a person owes, per kind
# ---------------------------------------------------------------------

def validate_fields(kind: str, payload: dict) -> None:
    """§1.3's own requirements, raised as `ValueError` (422 upstream).

    Checked at the POST (§3.3 ruling 2026-09-02), not left to apply: a
    missing `reason` is not a race, it is a form the person is still
    looking at. Left to the daemon's tick it comes back minutes later as
    a `rejected` row in a receipt nobody is watching, and the person's
    only signal is that nothing happened.

    The applier calls this too, so the two answers cannot diverge — a row
    can reach the queue by another route (a replay, a hand-written row),
    and the requirement is the same one either way.

    These are §1.3's requirements, NOT the Strategist's: the pairing rule
    (`ConfirmShelve` needs an `Inject`), the delegation justification —
    those bind the machine, which may never stop itself, and a person is
    exactly the actor they do not bind.
    """
    tid = target_of(kind, payload)

    def _needs(field: str, why: str) -> None:
        if not str(payload.get(field) or "").strip():
            raise ValueError(f"{kind} requires `{field}` — {why} (§1.3)")

    if kind == "ConfirmShelve":
        if tid is None:
            raise ValueError("ConfirmShelve requires target_goal_id")
        _needs("reason", "a person's park is TERMINAL, and the reason is "
                         "the only record of why this line was stopped")
    elif kind == "ReturnToParent":
        if tid is None:
            raise ValueError("ReturnToParent requires group_id")
        _needs("reason", "closing a group retires every line under it, "
                         "and the parent is owed the why")
    elif kind == "Inject":
        _needs("proof", "the `## Proof` the formalizer is to settle — "
                        "the statement and the argument for it, as you "
                        "would write them for a colleague")
    elif kind == "MarkDeliverable":
        if tid is None:
            raise ValueError("MarkDeliverable requires target_goal_id")
    elif kind == "Delegate":
        # With a `target_goal_id` a person owes NEITHER charter nor
        # reason (§1.3): the goal's own statement is the charter, and a
        # person owes no justification for handing work down.
        if tid is None and not str(payload.get("charter") or "").strip():
            raise ValueError(
                "Delegate needs either a `charter` (the claim the new "
                "group must settle) or a `target_goal_id` to take one "
                "from")


# ---------------------------------------------------------------------
# enqueue
# ---------------------------------------------------------------------

def enqueue(conn: sqlite3.Connection, *, problem: str, kind: str,
            payload: dict, idempotency_key: str,
            expected_revision: "int | None" = None) -> int:
    """Queue one command; returns its id (the receipt).

    A repeated `idempotency_key` returns the EXISTING id — a retried
    POST (double-click, dropped response) must not become a second
    command. Two refusal types, the `state/projects.py` shape:
    `ValueError` = the request is malformed (422 upstream), `KeyError` =
    the named problem is not there (404).
    """
    if kind not in KINDS:
        raise ValueError(
            f"unknown command kind {kind!r}; expected one of "
            f"{sorted(KINDS)}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object (the strategist "
                         "decision's own fields)")
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("idempotency_key is required — it is what makes "
                         "a retried command the same command")
    # The named thing first, the form second: a command against a problem
    # that is not there is a 404 whatever its payload says, and reporting
    # the missing `reason` of a command nobody could ever apply sends the
    # person to fix the wrong half.
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (problem,)).fetchone() is None:
        raise KeyError(problem)
    validate_fields(kind, payload)
    existing = conn.execute(
        "SELECT id FROM human_commands WHERE idempotency_key = ?",
        (key,)).fetchone()
    if existing is not None:
        return int(existing["id"])
    cur = conn.execute(
        "INSERT INTO human_commands (problem, kind, payload,"
        " idempotency_key, expected_revision, status, created_at)"
        " VALUES (?, ?, ?, ?, ?, 'queued', ?)",
        (problem, kind, json.dumps(payload, ensure_ascii=False), key,
         (None if expected_revision is None else int(expected_revision)),
         db.now()))
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------
# preview (§1.3: a cascading command pops a confirm window first)
# ---------------------------------------------------------------------

def _goal_entry(conn: sqlite3.Connection, goal_id: int,
                effect: str) -> "dict | None":
    g = db.get_goal(conn, int(goal_id))
    if g is None:
        return None
    return {"id": int(g["id"]), "kind": "goal", "slug": str(g["slug"]),
            "status": str(g["status"]), "effect": effect}


def _group_entry(row, effect: str) -> dict:
    charter = str(row["charter"] or "").strip().splitlines()
    return {"id": int(row["id"]), "kind": "group",
            "slug": (charter[0][:120] if charter else f"group {row['id']}"),
            "status": str(row["status"]), "effect": effect}


def preview(conn: sqlite3.Connection, *, problem: str, kind: str,
            payload: dict) -> dict:
    """What this command would close, without closing anything.

    §1.3: a command that CASCADES must pop a confirm window first, and a
    window can only be honest if it names the nodes. The sets come from
    the cascade's own reasoning — `transitions.shelve_cascade_targets`
    (the read half of `_cascade_shelve_descendants`) and
    `groups.children` (the walk `groups.set_status` takes) — so preview
    and apply cannot drift apart. Nothing here writes, and nothing runs
    inside a transaction that would have to be rolled back: the two
    cascades were split into a read half and a write half instead, which
    is the only version that stays true when the appliers commit
    mid-cascade (they do).

    `revision` rides along so the confirm window can hand it straight
    back as the command's `expected_revision` — the read the person acted
    on and the command they issued then name the same state.
    """
    from . import groups as _groups

    out: "dict" = {"affected": [], "cascade": False,
                   "revision": revision(conn, kind=kind, payload=payload)}
    tid = target_of(kind, payload)
    if tid is None:
        return out
    if kind == "ConfirmShelve":
        head = _goal_entry(conn, tid, "shelved")
        if head is None:
            return out
        from . import transitions as _transitions
        rest = [_goal_entry(conn, g, "shelved")
                for g in _transitions.shelve_cascade_targets(conn, tid)]
        out["affected"] = [head] + [r for r in rest if r is not None]
        out["cascade"] = len(out["affected"]) > 1
        return out
    if kind == "ReturnToParent":
        me = _groups.get(conn, tid)
        if me is None or str(me["problem"]) != problem:
            return out
        rows = [_group_entry(me, "returned")]
        # A retired charter retires the work it delegated: every ACTIVE
        # descendant group is closed under it, and each closed group
        # parks its anchor (`groups.set_status` → `park_group_anchor`).
        frontier = [int(me["id"])]
        seen: "set[int]" = set()
        anchors: "list[int]" = [] if me["anchor_goal_id"] is None \
            else [int(me["anchor_goal_id"])]
        while frontier:
            nxt: "list[int]" = []
            for gid in frontier:
                if gid in seen:
                    continue
                seen.add(gid)
                for kid in _groups.children(conn, gid):
                    if str(kid["status"]) != _groups.ACTIVE:
                        continue
                    rows.append(_group_entry(kid, "closed"))
                    if kid["anchor_goal_id"] is not None:
                        anchors.append(int(kid["anchor_goal_id"]))
                    nxt.append(int(kid["id"]))
            frontier = nxt
        from . import transitions as _transitions
        for anchor in anchors:
            g = db.get_goal(conn, anchor)
            if g is None or str(g["status"]) not in (
                    "open", "attempting", "pending_strategist_review",
                    "frozen"):
                continue
            entry = _goal_entry(conn, anchor, "shelved")
            if entry is not None:
                rows.append(entry)
            rows += [e for e in
                     (_goal_entry(conn, g2, "shelved") for g2 in
                      _transitions.shelve_cascade_targets(conn, anchor))
                     if e is not None]
        out["affected"] = rows
        out["cascade"] = len(rows) > 1
        return out
    return out


# ---------------------------------------------------------------------
# the applier (daemon side)
# ---------------------------------------------------------------------

def _decision_for(conn: sqlite3.Connection, *, problem: str, kind: str,
                  payload: dict):
    """Build the `Decision` the strategist appliers consume, applying
    §1.3's human-side exemptions. Raises ValueError with a message the
    person can act on."""
    from ..pipeline.strategist.model import parse_decision

    if kind == "FetchPaper":
        raise ValueError(_FETCHPAPER_REFUSAL)
    # The same per-kind requirements the POST refused on. A row can reach
    # the queue by another route (a replay, a hand-written row), and the
    # two answers must not be able to diverge.
    validate_fields(kind, payload)
    decision, err = parse_decision(json.dumps({**payload, "kind": kind}))
    if decision is None:
        raise ValueError(err)
    tid = target_of(kind, payload)
    if kind not in GROUP_TARGETED and tid is not None:
        g = db.get_goal(conn, tid)
        if g is None or str(g["problem"]) != problem:
            raise ValueError(
                f"target_goal_id={tid} is not a goal of {problem!r}")
        decision.target_id = int(g["id"])
    if kind == "Delegate" and not str(decision.brief or "").strip():
        # §1.3: with a `target_goal_id` the person owes no charter. The
        # applier needs one anyway — it is the child group's fixed
        # reference point, what its own Adversary judges against — so it
        # is taken from the goal being handed over. Nothing is invented:
        # the claim IS the statement.
        decision.brief = str(db.get_goal(conn, tid)["statement"])
    if kind == "ReturnToParent":
        from . import groups as _groups
        grp = _groups.get(conn, tid) if tid is not None else None
        if grp is None or str(grp["problem"]) != problem:
            raise ValueError(
                f"group_id={tid} is not a group of {problem!r}")
        if not str(decision.payload.get("flavour") or "").strip():
            decision.payload["flavour"] = "exhausted"
    return decision


def _group_for(conn: sqlite3.Connection, *, problem: str, kind: str,
               payload: dict) -> "int | None":
    """Which group's ledger the row is filed under. `ReturnToParent`
    names its own group; a goal-targeted command is filed with the group
    that OWNS the goal (`groups.group_for_goal`), so the human decision
    appears where the work it touches is being argued. None = the
    problem's top group (`commit_decisions` resolves it)."""
    from . import groups as _groups
    tid = target_of(kind, payload)
    if kind == "ReturnToParent":
        return tid
    if tid is None:
        return None
    row = _groups.group_for_goal(conn, problem, tid)
    return None if row is None else int(row["id"])


def _finish(conn: sqlite3.Connection, command_id: int, *, status: str,
            outcome: "str | None", decision_id: "int | None" = None) -> dict:
    conn.execute(
        "UPDATE human_commands SET status = ?, outcome = ?,"
        " decision_id = ?, applied_at = ? WHERE id = ?",
        (status, outcome, decision_id, db.now(), int(command_id)))
    conn.commit()
    return get(conn, command_id)  # type: ignore[return-value]


def apply_pending(conn: sqlite3.Connection, workspace: Path) -> "list[dict]":
    """Apply every queued command; returns the finished rows.

    Called once per dispatcher tick. A single row's failure is a
    `rejected` row carrying the reason, never an exception out of this
    function: the queue is a guest in the daemon's loop and must not be
    able to wedge it.
    """
    from ..pipeline.strategist import commit as _commit

    out: "list[dict]" = []
    for row in pending(conn):
        cid = row["id"]
        if str(row["outcome"] or "").startswith(ATTEMPT_MARK):
            out.append(_finish(
                conn, cid, status="rejected",
                outcome=("interrupted — a previous attempt started "
                         "applying this command and did not finish; "
                         "re-issue it (with a new idempotency key) "
                         "after checking what landed")))
            continue
        if row["expected_revision"] is not None:
            now_rev = revision(conn, kind=row["kind"], payload=row["payload"])
            if now_rev != row["expected_revision"]:
                out.append(_finish(conn, cid, status="rejected",
                                   outcome="stale"))
                continue
        try:
            decision = _decision_for(conn, problem=row["problem"],
                                     kind=row["kind"], payload=row["payload"])
            group_id = _group_for(conn, problem=row["problem"],
                                  kind=row["kind"], payload=row["payload"])
        except (ValueError, KeyError) as e:
            out.append(_finish(conn, cid, status="rejected",
                               outcome=str(e.args[0] if e.args else e)))
            continue
        conn.execute(
            "UPDATE human_commands SET outcome = ? WHERE id = ?",
            (f"{ATTEMPT_MARK} {db.now()}", cid))
        conn.commit()
        try:
            outcome = _commit.commit_decisions(
                [decision], conn, problem=row["problem"], tick=0,
                trigger_kind="human", workspace=workspace,
                group_id=group_id, actor=_commit.ACTOR_HUMAN)[0]
        except Exception as e:  # noqa: BLE001 — one row, never the loop
            out.append(_finish(conn, cid, status="rejected",
                               outcome=f"{type(e).__name__}: {e}"))
            continue
        out.append(_finish(conn, cid, status="applied", outcome="committed",
                           decision_id=int(outcome.decision_row_id)))
    return out
