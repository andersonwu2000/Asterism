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
    "ConfirmShelve", "FetchPaper", "Inject", "Signal"})

#: §3.7's three kill signals. `Signal` is the one DYNAMIC command: every
#: other kind acts on a row, this one reaches an OS process — a person
#: stopping ONE in-flight Formalizer.
SIGNALS: frozenset[str] = frozenset({
    "return_to_parent", "shelve", "return_to_nl"})

#: What the killed pipeline's completion is cascaded as. §3.7: the kill
#: records the pipeline's outcome as its signal and lets the EXISTING
#: completion path finalise it — it invents no cascade of its own.
#:
#:   return_to_nl  the Formalizer's OWN decline token, reused verbatim.
#:                 The goal goes back to the Strategist as an NL question
#:                 (`transitions.cascade_one` → `_enqueue_strategist_
#:                 review`), which is exactly what the worker's own
#:                 `-- decline: return_to_nl` does.
#:   shelve /      already settled, by the human decision the applier
#:   return_to_parent
#:                 files below. Their pipeline's own result must
#:                 therefore decide NOTHING further, and `moot` is the
#:                 framework's existing word for that: `cascade_one`
#:                 returns on it — no attempts++, no dead_attempts row,
#:                 no state touched.
SIGNAL_CASCADE: "dict[str, tuple[str, str]]" = {
    "return_to_nl": ("failed", "return_to_nl"),
    "shelve": ("moot", ""),
    "return_to_parent": ("moot", ""),
}

#: signal → the static command that finalises it, filed by the applier
#: through the SAME appliers §3.3 uses, with `actor='human'`.
#: `return_to_nl` files none: the cascade IS its whole semantics.
SIGNAL_DECISION: "dict[str, str]" = {
    "shelve": "ConfirmShelve",
    "return_to_parent": "ReturnToParent",
}

#: What the confirm window tells the person each signal will do.
SIGNAL_EFFECT: "dict[str, str]" = {
    "return_to_nl": ("the worker is killed and its goal goes back to the "
                     "Strategist as a natural-language question; the Lean "
                     "attempt in flight is lost and the goal's attempt "
                     "count rises by one"),
    "shelve": ("the worker is killed and you park the goal — a person's "
               "park is TERMINAL: nothing revives it and no paired "
               "Inject is owed"),
    "return_to_parent": ("the worker is killed and the group that owns "
                         "its goal returns to its parent with your "
                         "reason; every line under that charter is "
                         "retired with it"),
}

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
    "(`paper_search` / `paper_fetch`), or by uploading the pdf into the "
    "Project's documents yourself.")


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
    elif kind == "Signal":
        # §3.7. A kill is aimed at ONE pipeline id, never at a name or a
        # kind — that is the whole difference between this command and
        # the broad-filter sweep CLAUDE.md rule 8 exists about.
        if not str(payload.get("pipeline_id") or "").strip():
            raise ValueError(
                "Signal requires `pipeline_id` — a kill names the one "
                "worker it stops (§3.7)")
        sig = str(payload.get("signal") or "").strip()
        if sig not in SIGNALS:
            raise ValueError(
                f"Signal requires `signal` to be one of "
                f"{sorted(SIGNALS)}; got {sig!r}")
        if sig == "return_to_parent":
            _needs("reason", "closing a group from under a running "
                             "worker retires every line beneath it, and "
                             "the parent is owed the why")
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


def _preview_signal(conn: sqlite3.Connection, out: dict,
                    payload: dict) -> dict:
    """§3.7's confirm window: WHICH worker is about to be killed, and
    what stopping it does.

    The row is the pipeline's own — kind, target and `started_at`. The
    elapsed time is most of what tells a person whether they mean it: a
    Formalizer four minutes in and one forty minutes in are the same row
    and not the same decision. A pipeline id nobody knows returns
    `pipeline: None` rather than an error — the window says "there is no
    such worker", which is the answer.
    """
    pid = str(payload.get("pipeline_id") or "").strip()
    sig = str(payload.get("signal") or "").strip()
    out["effect"] = SIGNAL_EFFECT.get(sig, "")
    row = conn.execute(
        "SELECT id, kind, target_id, target_kind, status, started_at"
        " FROM pipelines WHERE id = ?", (pid,)).fetchone()
    if row is None:
        out["pipeline"] = None
        return out
    out["pipeline"] = {
        "id": str(row["id"]), "kind": str(row["kind"]),
        "target_id": str(row["target_id"]),
        "target_kind": str(row["target_kind"]),
        "status": str(row["status"]),
        "started_at": str(row["started_at"])}
    if str(row["target_kind"]) == "Goal":
        entry = _goal_entry(conn, int(row["target_id"]),
                            SIGNAL_CASCADE.get(sig, ("", ""))[1] or sig)
        if entry is not None:
            out["affected"] = [entry]
    return out


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
    if kind == "Signal":
        return _preview_signal(conn, out, payload)
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


def finalise_signalled(conn: sqlite3.Connection, sink, pipeline_id: str,
                       outcome: str,
                       failure_reason: str) -> "tuple[str, str]":  # noqa: ANN001
    """The dispatcher's side of §3.7, called once per completed pipeline.

    A killed worker does not know it was killed: it reports whatever its
    own death looked like from inside (a broken stream, a non-zero rc),
    and finalised on that the pipeline reads as an infra failure — the
    person's decision would be nowhere in the record. So the signal that
    was armed at kill time is taken here and substituted:

      * the `pipelines` row's OUTCOME becomes the signal, which is what
        makes "why did this stop?" answerable months later from the row
        itself rather than from a log nobody kept;
      * the (outcome, failure_reason) the EXISTING cascade is given
        becomes `SIGNAL_CASCADE`'s — no new transition, no new code path.

    Returns the pair to cascade with; unchanged for every pipeline no
    signal was armed for, which is all but a handful."""
    sig = None if sink is None else sink.take(str(pipeline_id))
    if sig is None:
        return outcome, failure_reason
    db.finish_pipeline(conn, pipeline_id=str(pipeline_id), status="failed",
                       outcome=f"human_signal:{sig}")
    return SIGNAL_CASCADE[sig]


def _stamp_attempt(conn: sqlite3.Connection, command_id: int) -> None:
    """Mark the row as being applied, in its own transaction. See
    `ATTEMPT_MARK`: the appliers commit as they go, so a crash between
    the mark and the effects must read as residue, not as work to redo."""
    conn.execute("UPDATE human_commands SET outcome = ? WHERE id = ?",
                 (f"{ATTEMPT_MARK} {db.now()}", int(command_id)))
    conn.commit()


def _apply_signal(conn: sqlite3.Connection, row: dict, *, workspace: Path,
                  sink) -> dict:  # noqa: ANN001 — a SignalSink, duck-typed
    """§3.7's kill: check, kill, finalise — in that order, and no other.

    `sink` is the daemon's spawn registry (`core/spawn_registry.
    SignalSink`), passed DOWN from the dispatcher loop rather than
    imported: the applier runs inside that loop and the two facts it
    needs — is this pipeline in THIS daemon's flight, and what process
    tree belongs to it — are the loop's, not the state layer's.

    The order is the whole safety property. If the kill did not happen,
    the park must not happen either: a goal a person has parked while its
    worker keeps writing into the workspace is the 2026-08-15 failure
    (a spawn recorded as dead went on calling gateway tools for five
    minutes) with a person's signature on it. So every refusal below
    returns before the decision is filed.
    """
    from ..pipeline.strategist import commit as _commit
    from . import groups as _groups

    cid = row["id"]
    payload = row["payload"]
    try:
        validate_fields("Signal", payload)
    except ValueError as e:
        return _finish(conn, cid, status="rejected",
                       outcome=str(e.args[0] if e.args else e))
    pid = str(payload["pipeline_id"]).strip()
    sig = str(payload["signal"]).strip()

    p = conn.execute("SELECT * FROM pipelines WHERE id = ?",
                     (pid,)).fetchone()
    if p is None:
        return _finish(conn, cid, status="rejected", outcome=(
            f"no pipeline {pid!r} — nothing has ever run under that id"))
    # NAME the state actually found. A person whose kill did nothing must
    # not be left to guess which half of the sentence was wrong.
    if str(p["kind"]) != "Formalizer" or str(p["status"]) != "running":
        detail = (f" (finished {p['finished_at']})"
                  if p["finished_at"] else "")
        return _finish(conn, cid, status="rejected", outcome=(
            f"a signal stops an in-flight Formalizer; pipeline {pid} is a "
            f"{p['kind']} with status {p['status']!r}{detail}"))
    if sink is None:
        return _finish(conn, cid, status="rejected", outcome=(
            "no spawn registry on this applier — a kill signal can only "
            "be applied by the daemon that owns the spawn"))

    _stamp_attempt(conn, cid)
    try:
        killed = sink.deliver(pid, sig)
    except Exception as e:  # noqa: BLE001 — one row, never the loop
        return _finish(conn, cid, status="rejected",
                       outcome=str(e.args[0] if e.args else e))
    note = f"{sig}: killed {killed} process tree(s)"

    decision_kind = SIGNAL_DECISION.get(sig)
    if decision_kind is None:
        # `return_to_nl`: the goal's return to the NL layer IS the killed
        # pipeline's own cascade (`SIGNAL_CASCADE`). Nothing to file, and
        # nothing re-dispatched by the signal itself (§3.7).
        return _finish(conn, cid, status="applied", outcome=note)

    if str(p["target_kind"]) != "Goal":
        return _finish(conn, cid, status="rejected", outcome=(
            f"{note}; but pipeline {pid} targets a {p['target_kind']}, "
            f"not a Goal — {decision_kind} has nothing to act on"))
    goal_id = int(p["target_id"])
    reason = (str(payload.get("reason") or "").strip()
              or f"stopped in flight by a human {sig} signal (§3.7)")
    if decision_kind == "ConfirmShelve":
        sub = {"target_goal_id": goal_id, "reason": reason}
    else:
        grp = _groups.group_for_goal(conn, row["problem"], goal_id)
        if grp is None:
            return _finish(conn, cid, status="rejected", outcome=(
                f"{note}; but no group owns goal {goal_id}, so there is "
                f"no charter to return"))
        sub = {"group_id": int(grp["id"]), "reason": reason}
    try:
        decision = _decision_for(conn, problem=row["problem"],
                                 kind=decision_kind, payload=sub)
        outcome = _commit.commit_decisions(
            [decision], conn, problem=row["problem"], tick=0,
            trigger_kind="human", workspace=workspace,
            group_id=_group_for(conn, problem=row["problem"],
                                kind=decision_kind, payload=sub),
            actor=_commit.ACTOR_HUMAN)[0]
    except Exception as e:  # noqa: BLE001 — one row, never the loop
        # Loud and specific: the worker IS dead, and the finalisation is
        # not. That is a half-applied command and the receipt says so.
        return _finish(conn, cid, status="rejected", outcome=(
            f"{note}; but the {decision_kind} did not land — "
            f"{type(e).__name__}: {e}"))
    return _finish(conn, cid, status="applied",
                   outcome=f"{note}; {decision_kind} filed",
                   decision_id=int(outcome.decision_row_id))


def apply_pending(conn: sqlite3.Connection, workspace: Path,
                  *, signal_sink=None) -> "list[dict]":  # noqa: ANN001
    """Apply every queued command; returns the finished rows.

    Called once per dispatcher tick. A single row's failure is a
    `rejected` row carrying the reason, never an exception out of this
    function: the queue is a guest in the daemon's loop and must not be
    able to wedge it.

    `signal_sink` is the daemon's spawn registry (`core/spawn_registry.
    SignalSink`), handed DOWN by the loop — §3.7's kill needs a process
    tree and an answer to "is this pipeline in THIS daemon's flight?",
    and neither is a thing `state/` may reach up for. None means no
    registry, and a `Signal` is then refused rather than faked.
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
        if row["kind"] == "Signal":
            # §3.7: the one command whose effect is an OS process, so it
            # has its own applier — the appliers below all take a
            # `Decision` and a target row, and a signal has neither.
            out.append(_apply_signal(conn, row, workspace=workspace,
                                     sink=signal_sink))
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
        _stamp_attempt(conn, cid)
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
