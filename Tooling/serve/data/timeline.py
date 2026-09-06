"""Timeline — the flat event log (`problem_events`) whose every row
reads `at | what | to whom` — plus everything downstream of the file's
own "Timeline" section marker: Programme reads (`programme`,
`_programme_events`, `_programme_rev` — moved up from their original
position between `problem_detail` and this section, see the package
docstring), the discussion-group tree (`groups_of` and kin),
goal/strategy drill-down (`goal_detail`, `strategy_detail`), and the
review/bridged-library-index leaves that happened to sit in the same
span (`review`, `signoff_with_seal`, `library`). `inbox`/`inbox_count`
sat here too until 2026-09-02, when they moved (unchanged) to
`human_inbox.py`.

Split out of `data.py` 2026-08-28 (Phase B, B3). `edges.py`'s
`problem_detail` imports several names back from here
(`_disproof_links`, `_goal_signature`, `_programme_events`,
`_programme_rev`, `_top_group_id`, `groups_of`) — this module carries
no import from `edges.py` in return, so the package stays acyclic.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

from ...state import db, transitions
from . import _link_kind_expr


#: v35 — every group owns its own revision chain, numbered from 1. A
#: problem-wide read therefore interleaves N chains and its "latest
#: rev" is the max of unrelated numberings: rev 3 of one argument
#: displayed as the successor of rev 2 of another. Every read below
#: scopes to ONE group, defaulting to the top group — the one whose
#: argument the problem page is about.
def _group_clause(gid: "int | None") -> "tuple[str, tuple]":
    return (" AND group_id = ?", (gid,)) if gid is not None else ("", ())


def _programme_events(conn: sqlite3.Connection, problem: str,
                      group_id: "int | None" = None) -> "list[dict]":
    clause, args = _group_clause(group_id)
    try:
        return [{
            "id": int(r["id"]),
            "rev": int(r["rev"]),
            "status": str(r["status"]),
            "rounds": int(r["rounds"]),
            "created_at": str(r["created_at"]),
            "group_id": (None if r["group_id"] is None
                         else int(r["group_id"])),
        } for r in conn.execute(
            "SELECT id, rev, status, rounds, created_at, group_id"
            " FROM programme_revisions WHERE problem = ?" + clause +
            " ORDER BY id DESC LIMIT 100", (problem,) + args)]
    except sqlite3.OperationalError:
        return []  # pre-v30 DB


def _programme_rev(conn: sqlite3.Connection, problem: str,
                   group_id: "int | None" = None) -> "int | None":
    clause, args = _group_clause(group_id)
    try:
        row = conn.execute(
            "SELECT MAX(rev) FROM programme_revisions"
            " WHERE problem = ? AND status = 'passed'" + clause,
            (problem,) + args).fetchone()
        return int(row[0]) if row and row[0] is not None else None
    except sqlite3.OperationalError:
        return None  # pre-v30 DB opened read-only — no table, no tab


def programme(conn: sqlite3.Connection, problem: str,
              group_id: "int | None" = None) -> dict:
    """The Programme page read: current passed revision (full body) +
    the whole revision history (passed AND rejected, no bodies — the
    audit dialogue stays in the DB; design §2 keeps the render clean).

    Verdict reservations ride along for the current rev: they are the
    Adversary's on-the-record caveats, exactly what a reader signing
    off on the argument should see.

    One GROUP's chain (v35) — `group_id` defaults to the top group, the
    argument the problem page is about. `groups` names the others so a
    reader can tell that a delegated burden is arguing elsewhere."""
    if group_id is None:
        group_id = _top_group_id(conn, problem)
    clause, args = _group_clause(group_id)
    rows = conn.execute(
        "SELECT id, rev, status, verdict, rounds, created_at"
        " FROM programme_revisions WHERE problem = ?" + clause +
        " ORDER BY id DESC", (problem,) + args).fetchall()
    history = [{
        "rev": int(r["rev"]),
        "status": str(r["status"]),
        "rounds": int(r["rounds"]),
        "created_at": str(r["created_at"]),
    } for r in rows]
    cur = conn.execute(
        "SELECT rev, body, verdict, rounds, created_at"
        " FROM programme_revisions"
        " WHERE problem = ? AND status = 'passed'" + clause +
        " ORDER BY rev DESC LIMIT 1", (problem,) + args).fetchone()
    current = None
    if cur is not None:
        reservations: "list[str]" = []
        try:
            v = json.loads(cur["verdict"] or "{}")
            reservations = [str(x) for x in (v.get("reservations") or [])]
        except (TypeError, ValueError):
            pass
        current = {
            "rev": int(cur["rev"]),
            "body": str(cur["body"]),
            "rounds": int(cur["rounds"]),
            "created_at": str(cur["created_at"]),
            "reservations": reservations,
        }
    # (The previous passed body rode along here for a rev-to-rev diff.
    # The owner reads only the standing argument — 2026-08-07 — and a
    # whole spare body on every 15s poll is not worth carrying for a
    # panel nobody opens.)
    # The charter of the group being READ, in full — the reason this
    # argument exists at all. The cards carry a snippet for labels;
    # the whole claim belongs in the reading, not in a tooltip.
    charter = None
    if group_id is not None:
        row = conn.execute(
            "SELECT charter, parent_group_id FROM groups WHERE id = ?",
            (int(group_id),)).fetchone()
        if row is not None and row["parent_group_id"] is not None:
            charter = str(row["charter"] or "") or None
    return {"current": current, "history": history,
            "group_id": group_id, "charter": charter,
            "groups": groups_of(conn, problem)}



# ---------------------------------------------------------------------
# Timeline — one flat log whose every row reads `at | what | to whom`
# ---------------------------------------------------------------------

#: decision_kind → the log's verb. A CLOSED vocabulary: a row states
#: what happened in one token and NAMES the object it happened to.
#: Prose (the brief, the reason) is expansion material and never the
#: headline — a timeline whose rows opened with 1.3KB of roadmap
#: markdown was unreadable at a glance (owner, 2026-08-07). An unknown
#: kind keeps its engine name rather than being mislabelled.
_DECISION_VERB: "dict[str, str]" = {
    "Inject": "asked",
    "Reopen": "reopened",
    "ConfirmShelve": "shelved",
    "MarkDeliverable": "deliverable",
    "Ingest": "ingested",
    "FetchPaper": "paper",
    "Delegate": "handed_off",
    "ReturnToParent": "handed_back",
    "CloseGroup": "closed_group",
    "RequestUserAmend": "asked_you",
    "EmitDirective": "directive",
    "Noop": "held",
    "AttemptDisproof": "disproof",
    # v52 — the theory layer's request. Not a dispatch of proof work:
    # what comes back is a DOCUMENT, so the verb says what was asked
    # for, not who was sent (theory_wake_design.md §2).
    "Theorize": "asked_theory",
}

# The theory layer's other five verbs are NOT decision verbs and so are
# not in that table: `theorizing`/`theorized` are the WAKE (a `pipelines`
# row — when the author started, when it came back and with what) and
# `theory`/`theory_refused`/`theory_died` are the ANSWER — the document
# that landed, the refusal that landed nothing (both a `theory_documents`
# row), or NO row at all, which is its own answer: the wake died before
# anything was ruled on. All six are `object_kind='theory'` and all six
# name the OBJECTIVE, which is the only string a reader can follow one
# request by. `_theory_events` below writes the five.

#: How much of an objective a row carries as its NAME. The objective is
#: a REQUEST, not a title — the strategist prompt asks for a statement
#: plus the wall around it, and the ones in the wild run to paragraphs.
#: Same law the Programme's title gets: the headline is the first line,
#: capped; the rest is expansion material.
_OBJECTIVE_LABEL = 120

#: decision outcomes that mean "the thing it asked for exists now" —
#: the moment the produced goal became real. Mirrors the UI's OK set;
#: `parse` failures and declines are NOT landings.
_LANDED_OUTCOMES = frozenset({
    "success", "accepted", "live_subgoal", "closed_subgoal", "proved",
})

#: goal statuses that are an end of the road — these get a dated event.
#: An open/attempting goal has no transition to date yet. (Reads the
#: CURRENT status, so retired vocabulary does not belong here — unlike
#: `_TO_STATUS_VERB` below, which reads historical `goal_events` rows.)
_TERMINAL_GOAL_STATES = {
    "proved": "proved",
    "shelved": "shelved",
    "disproved": "disproved",
}

#: `goal_events.to_status` → the log's verb (v36). Not every transition
#: is news: 'attempting' is a worker picking the goal up and 'open' from
#: 'attempting' is the same worker putting it down, which the attempt
#: rows already tell. A revival — 'open' from a SETTLED state — is news,
#: and gets its verb from the from-side below.
_TO_STATUS_VERB = {
    "proved": "proved",
    "shelved": "shelved",
    "disproved": "disproved",
    "frozen": "frozen",
    "pending_strategist_review": "for_review",
    # HISTORY ONLY: the goal status `dead` retired at v51 (2026-09-04)
    # and no new row can carry it, but the rows written before that date
    # are still in `goal_events` and are still the log of what happened.
    # Dropping the verb would silently blank them.
    "dead": "dead",
}
_SETTLED = transitions.GOAL_TERMINALS

#: how far along a goal's life each verb sits — the tiebreaker when a
#: brick is asked for and lands inside the same clock minute
_LIFE_RANK: "dict[str, int]" = {
    "opened": 0, "asked": 1, "reopened": 1, "hiccup": 2, "failed": 3,
    "deliverable": 6, "proved": 7, "shelved": 7, "disproved": 7,
    "dead": 7, "ingested": 8,
    # the theory request's own life, in the order the writers run it:
    # the decision is filed, the wake starts, the document row is
    # written INSIDE the pipeline, and only then does `finish_pipeline`
    # stamp the wake's end.
    "asked_theory": 1, "theorizing": 2, "theory": 6,
    "theory_refused": 6, "theory_died": 6, "theorized": 7,
}

#: What a dispatch ASKED FOR, when its goal does not exist yet (a
#: failed or still-in-flight Inject). Used ONLY to LABEL such a row —
#: never to link, never as a gate signal; with no row to point at the
#: alternative is an anonymous event, which is worst exactly where the
#: reader most wants a name (the newest dispatches).
#:
#: The PATH is tried first and the prose second, because the path is a
#: convention the framework enforces (`proofs/L_<slug>.lean`) while the
#: sentence around it is the strategist's own wording — and that wording
#: moved: batches now say "Mint into `proofs/L_x.lean`" with no "mint
#: brick `x`" anywhere, so a prose-only reader labelled the newest rows
#: with the problem's name (owner spotted it on union_closed,
#: 2026-08-09).
#: Three readers, most-structural first. The PATH is the file the brick
#: will actually be called, and the framework enforces its shape. The
#: TITLE is the brief's own opening line and every brief has one, but it
#: is the strategist's composition. The PROSE phrase is the weakest and
#: the one already caught moving. When a brief carries several they
#: agree; when they disagree the file name is the fact.
_MINT_READERS = (
    re.compile(r"proofs/L_([A-Za-z0-9_']+)\.lean"),
    re.compile(r"^#\s*[`\"]([A-Za-z0-9_']+)[`\"]", re.M),
    re.compile(r"[Mm]int (?:brick|def) [`\"]([A-Za-z0-9_']+)[`\"]"),
)


def _asked_for(brief: str) -> "str | None":
    for rx in _MINT_READERS:
        m = rx.search(brief)
        if m:
            return m.group(1)
    return None


def _objective_label(objective: str) -> "str | None":
    """An objective's first non-empty line, capped at `_OBJECTIVE_LABEL`
    — what a theory row calls itself. None when there is nothing to
    read, so the caller can fall back rather than render a blank."""
    for raw in str(objective or "").splitlines():
        line = raw.strip()
        if line == "":
            continue
        return line[:_OBJECTIVE_LABEL] or None
    return None


def _ev(at: str, kind: str, *, object_kind: str = "problem",
        label: str = "", goal_id: "int | None" = None,
        n: "int | None" = None, note: "str | None" = None,
        body: "str | None" = None, approx: bool = False,
        eid: str = "", batch_id: "str | None" = None,
        group_id: "int | None" = None,
        object_group_id: "int | None" = None,
        rev_id: "int | None" = None, path: "str | None" = None,
        actor: str = "strategist") -> dict:
    # `group_id` = which ARGUMENT this event belongs to (v35). A problem
    # under real load runs several discussion groups at once — 7 on
    # simple_loop_conjecture, 4 on union_closed — and their bricks
    # interleave in one stream with nothing to tell them apart.
    # `object_group_id` is different: the group a handover row is ABOUT.
    return {
        "at": at, "kind": kind, "object_kind": object_kind,
        "label": label, "goal_id": goal_id, "n": n, "note": note,
        "body": body, "approx": approx, "id": eid,
        "batch_id": batch_id, "group_id": group_id,
        "object_group_id": object_group_id,
        # the programme_revisions row this event IS — the key the
        # verdict read takes. `rev` cannot serve: a rejected proposal
        # and the revision that later takes its number are both `rev
        # N` of the same group (union_closed group 382 has seven rev
        # 1 rows), so the row id is the only handle that names one.
        "rev_id": rev_id,
        # the artifact this event LANDED, workspace-relative — filled
        # only by an accepted theory document, whose whole point is a
        # file the reader can open. A refusal carries None because it
        # landed nothing, and a dead link would be worse than silence.
        "path": path,
        # who decided (v48, HID §3.2). Semantic, not an audit label: a
        # person's ConfirmShelve is a terminal stop, and a row that does
        # not say so offers it to the reader as a peer's opinion.
        "actor": actor,
    }


def _logged_transitions(conn: sqlite3.Connection, problem: str,
                        goals: "list[dict]") -> "tuple[list[dict], set[int]]":
    """Goal state changes as the ENGINE RECORDED THEM (`goal_events`,
    v36 — appended inside `db.update_goal_status`, so it catches the
    operator's own amend escape hatch as well as every checked
    transition).

    Returns the events and the set of goals it speaks for: a goal with
    logged history is never reconstructed on top of.
    """
    by_id = {int(g["id"]): g for g in goals}
    out: "list[dict]" = []
    covered: "set[int]" = set()
    try:
        rows = conn.execute(
            "SELECT id, goal_id, from_status, to_status, event, reason, at"
            " FROM goal_events WHERE problem = ? ORDER BY at, id",
            (problem,)).fetchall()
    except sqlite3.OperationalError:
        return [], set()  # pre-v36 DB — reconstruction carries it all
    for r in rows:
        gid = int(r["goal_id"])
        if gid not in by_id:
            continue
        covered.add(gid)
        frm, to = str(r["from_status"] or ""), str(r["to_status"])
        verb = _TO_STATUS_VERB.get(to)
        if verb is None:
            # a revival is news; a worker picking the goal up is not
            if to == "open" and frm in _SETTLED:
                verb = "reopened"
            else:
                continue
        out.append(_ev(
            str(r["at"]), verb, object_kind="goal",
            label=str(by_id[gid]["slug"]), goal_id=gid,
            note=str(r["reason"] or "") or None,
            eid=f"e{int(r['id'])}"))
    return out, covered


def _transition_events(conn: sqlite3.Connection, problem: str,
                       goals: "list[dict]",
                       dec_rows: "list[sqlite3.Row]") -> "list[dict]":
    """When each goal reached its terminal state, for the goals the
    engine's own log does not cover — everything that happened before
    `goal_events` existed (v36).

    THE HONEST CAVEAT: this is RECONSTRUCTION. In order of trust:

      1. the succeeded pipeline that targeted the goal (`finished_at`)
      2. the producing decision's outcome write (`updated_at`) — when
         the batch step was recorded as landed
      3. `goals.updated_at`, marked `approx`

    (3) is last because that column is bumped by `attempts + 1`,
    `is_deliverable` and `integrity_verified` writes too: measured
    against (1)/(2) on Combinatorics.union_closed it agreed at the
    median and drifted +18min at p90, +43min worst case.
    """
    by_id = {int(g["id"]): g for g in goals}
    # (1) succeeded pipelines, latest per goal
    pipe: "dict[int, str]" = {}
    try:
        for r in conn.execute(
                "SELECT target_id, MAX(finished_at) AS at FROM pipelines"
                " WHERE target_kind = 'Goal' AND status = 'succeeded'"
                "   AND finished_at IS NOT NULL"
                " GROUP BY target_id"):
            try:
                gid = int(r["target_id"])
            except (TypeError, ValueError):
                continue
            if gid in by_id:
                pipe[gid] = str(r["at"])
    except sqlite3.OperationalError:
        pass
    # (2) the decision that produced the goal, once its outcome landed;
    # and (2b) the ConfirmShelve that set one aside — that decision IS
    # the shelving, so it dates it exactly.
    landed: "dict[int, str]" = {}
    shelved_by: "dict[int, str]" = {}
    for d in dec_rows:
        gid = d["produced_goal_id"]
        if (gid is not None and int(gid) in by_id
                and str(d["outcome"] or "") in _LANDED_OUTCOMES):
            landed[int(gid)] = str(d["updated_at"])
        if str(d["decision_kind"]) == "ConfirmShelve":
            try:
                tid = int(d["target_id"])
            except (TypeError, ValueError):
                continue
            if tid in by_id:
                shelved_by[tid] = str(d["created_at"])

    out: "list[dict]" = []
    for g in goals:
        kind = _TERMINAL_GOAL_STATES.get(str(g["status"]))
        if kind is None:
            continue
        gid = int(g["id"])
        # ConfirmShelve IS the shelving — its own row already says so.
        # (A ConfirmShelve on a goal that later revived stays: that one
        # is history, not a duplicate of the current state.)
        if kind == "shelved" and gid in shelved_by:
            continue
        at = pipe.get(gid) or landed.get(gid)
        approx = at is None
        if at is None:
            at = str(g["updated_at"])
        out.append(_ev(at, kind, object_kind="goal", label=str(g["slug"]),
                       goal_id=gid, approx=approx, eid=f"g{gid}"))
    return out


def _attempt_events(conn: sqlite3.Connection,
                    goals: "list[dict]") -> "list[dict]":
    """Failed attempts, numbered per goal in the order they happened.

    Infrastructure failures are split off as `hiccup`: the registry's
    own semantics — a provider/pipeline infra death never incremented
    `goals.attempts` — so counting them as attempts would tell the
    reader the machine tried more times than it did.
    """
    from ...state.failures import is_infra
    by_id = {int(g["id"]): g for g in goals}
    rows = []
    for r in conn.execute(
            "SELECT target_id, failure_reason, ts FROM dead_attempts"
            " WHERE target_kind = 'Goal' ORDER BY ts"):
        try:
            gid = int(r["target_id"])
        except (TypeError, ValueError):
            continue
        if gid in by_id:
            rows.append((gid, str(r["failure_reason"]), str(r["ts"])))
    out = []
    for i, (gid, reason, ts) in enumerate(rows):
        # NOT numbered. These rows are `dead_attempts` records — one per
        # failure the engine filed — and numbering them "attempt N"
        # claimed they were the engine's own attempt sequence. They are
        # not: measured on union_closed, `goals.attempts` disagrees in
        # BOTH directions (10 vs 6 recorded, 4 vs 6) because one spawn
        # can file two records (watchdog says stuck, then the spawn
        # times out) and some attempts burn the counter without filing
        # one. The reasons and their order are the evidence; the count
        # of tries belongs to whoever reads `goals.attempts`.
        out.append(_ev(ts, "hiccup" if is_infra(reason) else "failed",
                       object_kind="goal", label=str(by_id[gid]["slug"]),
                       goal_id=gid, note=reason, eid=f"a{i}-{gid}"))
    return out


def _decision_events(conn: sqlite3.Connection, problem: str,
                     dec_rows: "list[sqlite3.Row]",
                     goals: "list[dict]") -> "list[dict]":
    """The strategist's moves, each naming what it moved."""
    by_id = {int(g["id"]): g for g in goals}
    out = []
    for d in dec_rows:
        kind = str(d["decision_kind"])
        verb = _DECISION_VERB.get(kind, kind)
        try:
            payload = json.loads(d["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        # The Inject's argument is its named brick (2026-09-07); the
        # column answers only for legacy and human-filed rows.
        from ...state import programme as _programme
        brief = _programme.argument_for_decision(
            conn, d["id"], d["brief"])
        reason = str(d["reason"] or "")
        gid = d["produced_goal_id"]
        if gid is None:
            gid = d["target_id"]
        if gid is None:
            gid = payload.get("target_goal_id")
        try:
            gid = int(gid) if gid is not None else None
        except (TypeError, ValueError):
            gid = None
        if gid not in by_id:
            gid = None
        okind, label, obj_group = "problem", problem, None
        if gid is not None:
            okind, label = "goal", str(by_id[gid]["slug"])
        elif kind == "FetchPaper":
            okind = "paper"
            label = str(payload.get("query") or reason or "a paper")
        elif kind in ("Delegate", "ReturnToParent", "CloseGroup"):
            okind = "group"
            g = d["produced_group_id"] if "produced_group_id" \
                in d.keys() else None
            obj_group = int(g) if g is not None else (
                int(payload["group_id"]) if isinstance(
                    payload.get("group_id"), int) else None)
            # a group NAMES itself in its Programme's title; its charter
            # is a paragraph and a poor label (same law as the tree)
            card = _group_lineage(conn, problem, group_card(conn, obj_group)) \
                if obj_group else None
            label = (card or {}).get("title") or (card or {}).get(
                "charter") or (f"group {obj_group}" if obj_group else problem)
        elif kind == "Theorize":
            # a theory request names no goal and produces no group, so
            # every fallback above leaves it labelled with the PROBLEM.
            # What it names is the QUESTION — the objective the document
            # is asked to answer, and the string every other row of this
            # request is followed by.
            okind = "theory"
            label = (_objective_label(payload.get("objective") or "")
                     or reason or "a theory question")
        elif verb == "asked":
            # a dispatch whose brick does not exist yet (failed or still
            # in flight) — name what was ASKED FOR, or the row is anonymous
            # The brick's NAME is the answer outright since 2026-09-07
            # — no reader, no guess. The three prose readers below stay
            # for legacy and human-filed rows.
            named = (str(d["brick_name"] or "").strip()
                     if "brick_name" in d.keys() else "")
            asked = named or _asked_for(brief)
            if asked:
                okind, label = "unbuilt", asked
        note = reason or None
        if kind == "ReturnToParent" and payload.get("flavour"):
            note = f"{payload['flavour']} — {reason}" if reason \
                else str(payload["flavour"])
        own = d["group_id"] if "group_id" in d.keys() else None
        who = d["actor"] if "actor" in d.keys() else None
        out.append(_ev(
            str(d["created_at"]), verb, object_kind=okind, label=label,
            goal_id=gid, note=note, body=brief or None,
            eid=f"d{int(d['id'])}", batch_id=d["batch_id"],
            group_id=int(own) if own is not None else None,
            object_group_id=obj_group,
            actor=str(who or "strategist")))
    return out


def _theory_requests(dec_rows: "list[sqlite3.Row]") -> "tuple[dict, dict]":
    """The `Theorize` rows, indexed two ways.

      * by decision id — how a `theory_documents` row finds the request
        it answers (`decision_id` is the FK the landing writes).
      * by group, oldest first — how a PIPELINE finds it. A Theorist
        row is keyed by group and carries no decision id (the queue row
        that did is deleted when the unit finishes), so the request is
        the latest one FILED BEFORE the wake started. That is exact,
        not a guess: a group may have only one theory request in flight
        at a time (`verify_decision`, design §2), so no second candidate
        can sit in the same window.

    The request itself is `(batch_id, objective label)`; the group index
    keys it by `(created_at, decision id)` — the id breaks a same-second
    tie, and sorting on the payload instead would compare a NULL
    batch_id against a string and raise.
    """
    by_dec: "dict[int, tuple]" = {}
    by_group: "dict[int, list[tuple]]" = {}
    has_group = "group_id" in (dec_rows[0].keys() if dec_rows else ())
    for d in dec_rows:
        if str(d["decision_kind"]) != "Theorize":
            continue
        try:
            payload = json.loads(d["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        entry = (d["batch_id"],
                 _objective_label(payload.get("objective") or "")
                 or str(d["reason"] or "") or None)
        by_dec[int(d["id"])] = entry
        gid = d["group_id"] if has_group else None
        if gid is not None:
            by_group.setdefault(int(gid), []).append(
                (str(d["created_at"]), int(d["id"]), entry))
    for rows in by_group.values():
        rows.sort(key=lambda r: (r[0], r[1]))
    return by_dec, by_group


def _theory_events(conn: sqlite3.Connection, problem: str,
                   dec_rows: "list[sqlite3.Row]") -> "list[dict]":
    """The theory layer's life, minus its first quarter (the `Theorize`
    row is a decision and `_decision_events` files it).

    Outcomes are events too (owner, 2026-09-04): a request nobody can
    see, answered by a document nobody can see, is a whole layer running
    off the record. Three more rows per request, from the two tables the
    engine actually writes:

      `pipelines`         → the WAKE started (`theorizing`) and came
                            back (`theorized`, its note the outcome).
                            An infra death never reaches a document row,
                            and this pair is then the only trace of it.
      `theory_documents`  → the ANSWER: `theory` with the path it landed
                            and what the review cost, or `theory_refused`
                            with the rounds and — since the 2026-09-06
                            landing rule — the path of the record it
                            left.
                            NO row, on a wake that finished failed, is
                            the third answer and gets `theory_died`: the
                            spawn never came back, so no reviewer ever
                            ruled. Reading that as a refusal is what
                            union_closed g691 did twice on 2026-09-05.

    Every row carries the request's `batch_id`: a `Theorize` is an open
    batch step whose settlement is what wakes the group
    (`_maybe_enqueue_inject_batch_done`), so the answer's rows must name
    the batch the request does or the relay is invisible.
    """
    by_dec, by_group = _theory_requests(dec_rows)
    out: "list[dict]" = []
    # (1) the answers. Written INSIDE the pipeline, on both roads.
    # Keyed by pipeline id and carrying the PATH as well, because the
    # wake's own landing row (`theorized`) names the same document: the
    # log's third field is a name the reader can act on, and without the
    # path that click fell back to "follow this object" — the reader
    # asked for the document and got the request's history (2026-09-06).
    by_pipeline: "dict[str, tuple]" = {}
    try:
        docs = conn.execute(
            "SELECT id, group_id, pipeline_id, decision_id, objective,"
            " path, status, rounds, created_at FROM theory_documents"
            " WHERE problem = ? ORDER BY id", (problem,)).fetchall()
    except sqlite3.OperationalError:
        docs = []  # pre-v52 DB — the layer did not exist
    for r in docs:
        batch, asked = by_dec.get(
            int(r["decision_id"]) if r["decision_id"] is not None else -1,
            (None, None))
        label = (_objective_label(str(r["objective"] or "")) or asked
                 or "a theory question")
        gid = None if r["group_id"] is None else int(r["group_id"])
        accepted = str(r["status"]) == "accepted"
        out.append(_ev(
            str(r["created_at"]),
            "theory" if accepted else "theory_refused",
            object_kind="theory", label=label, n=int(r["rounds"]),
            # BOTH roads carry a path now (owner ruling 2026-09-06): a
            # refused document lands too, as the record of what was
            # tried, so the row opens it exactly as an accepted one is
            # opened. A row with no `path` — a refusal filed before that
            # rule — still offers none, which is right: the reader must
            # not be handed a link into a 404.
            path=(str(r["path"]) if r["path"] else None),
            eid=f"td{int(r['id'])}", batch_id=batch, group_id=gid))
        if r["pipeline_id"]:
            by_pipeline[str(r["pipeline_id"])] = (
                batch, label, str(r["path"]) if r["path"] else None)
    # (2) the wakes. `pipelines` carries no problem, and a Theorist row
    # is Group-targeted (worker.py) — so the problem's groups are the
    # key, exactly as the dispatcher wrote them (`str(int(group_id))`).
    try:
        gids = [int(r["id"]) for r in conn.execute(
            "SELECT id FROM groups WHERE problem = ?", (problem,))]
    except sqlite3.OperationalError:
        gids = []  # pre-v35 DB — no groups, hence no theory layer
    if not gids:
        return out
    rows = conn.execute(
        "SELECT id, target_id, status, outcome, started_at, finished_at"
        " FROM pipelines WHERE kind = 'Theorist' AND target_kind = 'Group'"
        f"   AND target_id IN ({','.join('?' * len(gids))})",
        tuple(str(g) for g in gids)).fetchall()
    for r in rows:
        pid = str(r["id"])
        try:
            gid = int(r["target_id"])
        except (TypeError, ValueError):
            gid = None
        answered = pid in by_pipeline
        batch, label, landed = by_pipeline.get(pid, (None, None, None))
        if label is None:
            # still in flight, or dead before review: the request it
            # answers is the last one filed before it started
            prior = [e for at, _id, e in by_group.get(gid, [])
                     if at <= str(r["started_at"])]
            batch, label = prior[-1] if prior else (None, None)
        if label is None:
            label = f"group {gid}" if gid is not None else problem
        out.append(_ev(str(r["started_at"]), "theorizing",
                       object_kind="theory", label=label,
                       eid=f"ts{pid}", batch_id=batch, group_id=gid))
        if r["finished_at"] and not answered and str(
                r["outcome"] or r["status"]) != "success":
            # The answer this road has. `answered` is the whole test:
            # a run that reached a ruling wrote its `theory_documents`
            # row above, so this fires exactly when none exists.
            out.append(_ev(
                str(r["finished_at"]), "theory_died", object_kind="theory",
                label=label, note=str(r["outcome"] or r["status"]),
                eid=f"tx{pid}", batch_id=batch, group_id=gid))
        if r["finished_at"]:
            out.append(_ev(
                str(r["finished_at"]), "theorized", object_kind="theory",
                label=label, note=str(r["outcome"] or r["status"]),
                # what the wake PRODUCED, where it produced one. A run
                # that died before any ruling landed no file and offers
                # no link, which is right: the reader must not be handed
                # a link into a 404.
                path=landed,
                eid=f"tf{pid}", batch_id=batch, group_id=gid))
    return out


def _goal_arguments(conn: sqlite3.Connection, problem: str,
                    dec_rows: "list[sqlite3.Row]",
                    goals: "list[dict]") -> "dict[int, int]":
    """goal id → the discussion group whose argument it serves.

    A commissioned brick inherits the group of the decision that asked
    for it. A subgoal nobody commissioned — cut out of a larger goal by
    a decomposition — serves the same argument as the goal it was cut
    from, so the attribution propagates down the strategy edges.
    """
    if "group_id" not in (dec_rows[0].keys() if dec_rows else ()):
        return {}
    arg: "dict[int, int]" = {}
    ids = {int(g["id"]) for g in goals}
    for d in dec_rows:
        gid, own = d["produced_goal_id"], d["group_id"]
        if gid is not None and own is not None and int(gid) in ids:
            arg[int(gid)] = int(own)
    parent: "dict[int, int]" = {}
    for r in conn.execute(
            "SELECT e.subgoal_id AS sub, s.goal_id AS parent"
            "  FROM strategy_subgoals e JOIN strategies s"
            "    ON s.id = e.strategy_id"
            # only the strategy that MINTED it is its parent — a route
            # that cites a lemma does not adopt it into its group
            # (state/programme.py:310 and state/transitions.py:979 have
            # always read it this way)
            f" WHERE {_link_kind_expr(conn)} = 'minted'"):
        if int(r["sub"]) in ids and int(r["parent"]) in ids:
            parent[int(r["sub"])] = int(r["parent"])
    for gid in ids - set(arg):
        seen, cur = set(), gid
        while cur in parent and cur not in seen:
            seen.add(cur)
            cur = parent[cur]
            if cur in arg:
                arg[gid] = arg[cur]
                break
    return arg


#: how far apart the two records of one act may sit. They are written
#: in the same operation (measured: under 0.1s), so this is slack for
#: clock granularity, not a window in which two real shelvings could be
#: mistaken for one — those are hours apart.
_SAME_ACT_SEC = 120.0


def _already_said(said: "set", e: dict) -> bool:
    """Has a decision row already reported this goal's transition?"""
    from datetime import datetime
    for gid, kind, at in said:
        if gid != e["goal_id"] or kind != e["kind"]:
            continue
        try:
            delta = abs((datetime.fromisoformat(at)
                         - datetime.fromisoformat(e["at"])).total_seconds())
        except ValueError:
            continue
        if delta <= _SAME_ACT_SEC:
            return True
    return False


def problem_events(conn: sqlite3.Connection, problem: str) -> dict:
    """The Timeline read: one flat, uniform log.

    Every row is `at | what happened | to whom`, and every row NAMES an
    object — which is what lets a reader follow one brick's whole life
    (asked → attempt 2 → proved) by filtering on it. That reading was
    impossible while the log recorded only what the strategist decided:
    of 54 goals on union_closed, 52 reached `proved` and not one of
    those landings appeared here (owner, 2026-08-07).
    """
    goals = [dict(r) for r in conn.execute(
        "SELECT id, slug, status, origin, created_at, updated_at"
        " FROM goals WHERE problem = ?", (problem,))]
    _dcols = {r[1] for r in conn.execute(
        "PRAGMA table_info(strategist_decisions)")}
    _gsel = "" if "produced_group_id" not in _dcols \
        else ", produced_group_id, group_id"
    # `actor` is v48 and semantic (HID §3.2) — see `_ev`.
    _gsel += ", actor" if "actor" in _dcols else ""
    dec_rows = conn.execute(
        "SELECT id, batch_id, decision_kind, target_id, brief,"
        " brick_name, reason,"
        " payload, outcome, produced_goal_id, created_at, updated_at"
        + _gsel +
        " FROM strategist_decisions WHERE problem = ?"
        " ORDER BY id DESC", (problem,)).fetchall()

    events = _decision_events(conn, problem, dec_rows, goals)
    logged, covered = _logged_transitions(conn, problem, goals)
    # A decision whose EXECUTION is a status write gets recorded twice:
    # once as what the strategist decided, once as what happened to the
    # goal. ConfirmShelve is the live instance (8 pairs on union_closed,
    # every delta under 0.1s — the status write rides the decision), and
    # Reopen has the same shape. Same fact, so one row; the DECISION
    # survives because it carries WHY, which the transition cannot.
    said = {(e["goal_id"], e["kind"], e["at"]) for e in events
            if e["goal_id"] is not None}
    events += [e for e in logged if not _already_said(said, e)]
    events += [e for e in _transition_events(conn, problem, goals, dec_rows)
               if e["goal_id"] not in covered]
    events += _attempt_events(conn, goals)
    # the theory layer's wake and its answer (v52). The `Theorize` row
    # itself is a decision and is already above.
    events += _theory_events(conn, problem, dec_rows)

    # a goal nobody dispatched (a decomposition cut it out of its
    # parent) still has a birthday, and its insert dates it exactly
    asked = {e["goal_id"] for e in events
             if e["kind"] in ("asked", "reopened") and e["goal_id"]}
    for g in goals:
        if int(g["id"]) not in asked:
            events.append(_ev(str(g["created_at"]), "opened",
                              object_kind="goal", label=str(g["slug"]),
                              goal_id=int(g["id"]),
                              note=str(g["origin"]),
                              eid=f"o{int(g['id'])}"))

    # The argument's own landmarks. A revision NAMES itself in its own
    # `# Title` — "programme" on every row said only which surface it
    # came from, not what changed (owner, 2026-08-07). substr: the title
    # is the first non-empty line and a body runs to tens of KB.
    #
    # Keyed by ROW, not by rev: the log carries every group's revisions
    # and `rev 28` names one row per group, so a rev-keyed title would
    # hand the top group's heading to somebody else's argument.
    #
    # Rejected proposals get their titles too. They read "Programme:
    # programme" while they had nothing to open; they now open onto the
    # ruling that killed them, and a row you can open is a row worth
    # naming.
    titles: "dict[int, str]" = {}
    try:
        for r in conn.execute(
                "SELECT id, substr(body, 1, 400) AS head FROM"
                " programme_revisions WHERE problem = ?", (problem,)):
            t = _programme_title(str(r["head"] or ""))
            if t:
                titles[int(r["id"])] = t
    except sqlite3.OperationalError:
        pass
    # EVERY group's revisions, not just the top one. A problem under
    # load argues several at once (4 on union_closed) and the delegated
    # ones do most of the arguing: on 2026-08-29 all five verdicts
    # carrying the new judge stamp sat in sub-groups, so a log scoped to
    # the top group showed none of them. The row names which argument it
    # serves through `group_id`, which is exactly why events carry one.
    for r in _programme_events(conn, problem, None):
        passed = r["status"] == "passed"
        events.append(_ev(
            r["created_at"], "rev" if passed else "proposal",
            object_kind="programme",
            label=titles.get(r["id"], "programme"), n=r["rev"],
            note=(None if r["rounds"] == 0 else
                  f"{r['rounds']} round{'' if r['rounds'] == 1 else 's'}"
                  " of review"),
            eid=f"p{r['id']}",
            group_id=r["group_id"], rev_id=r["id"]))

    # which argument each event serves — a decision knows its own group;
    # everything derived from a goal inherits the goal's
    arg = _goal_arguments(conn, problem, dec_rows, goals)
    for e in events:
        if e["group_id"] is None and e["goal_id"] is not None:
            e["group_id"] = arg.get(int(e["goal_id"]))

    # newest first; within one timestamp, later-in-life first — a brick
    # minted and landed inside the same minute must not read as having
    # been proved before it was asked for
    events.sort(key=lambda e: (e["at"], _LIFE_RANK.get(e["kind"], 5),
                               e["id"]), reverse=True)
    # Where the record starts. Below this line every goal landing is
    # dated by inference from the work that produced it; above it the
    # engine wrote the transition down itself. Three months from now
    # nobody will remember which half was which unless the surface
    # says so (backend, 2026-08-07).
    try:
        row = conn.execute(
            "SELECT MIN(at) FROM goal_events WHERE problem = ?",
            (problem,)).fetchone()
        log_since = str(row[0]) if row and row[0] is not None else None
    except sqlite3.OperationalError:
        log_since = None
    # names for the argument lenses. A problem with only its top group
    # reads exactly as it did before groups existed — the UI shows no
    # lens at all — so this list is furniture only when it is > 1.
    groups = [{
        "id": g["id"], "is_top": g["is_top"],
        "label": g.get("title") or g.get("charter") or f"group {g['id']}",
        "status": g["status"],
    } for g in groups_of(conn, problem)]
    return {"events": events, "log_since": log_since, "groups": groups}


# display-signature cache: mtime-keyed per lean file so the 3s detail
# poll doesn't re-read a hundred stubs (the underlying reader is the
# engine's context.goal_display_signature — ONE extraction, no serve
# dialect; #5, 2026-07-18)
#: {key: (mtime, signature, checked_at)}
_SIG_CACHE: "dict[str, tuple[float, str | None, float]]" = {}

#: How long a cached reading is trusted WITHOUT re-stat'ing its file.
#: Being mtime-keyed still cost one `stat()` per goal per request —
#: 370 syscalls on a 370-goal task, every 2s, to learn that nothing had
#: changed. A signature is display text: a file that changes reaches
#: the screen a second later either way.
_SIG_STAT_TTL = 2.0


def _goal_signature(workspace: Path, slug: str,
                    lean_path: "str | None",
                    statement: "str | None") -> "str | None":
    """Binders+conclusion display form, or None when the file offers
    nothing beyond the stored statement (alias bodies read as plumbing,
    not mathematics — the bare statement is more honest there)."""
    if not lean_path:
        return None
    key = f"{workspace}|{lean_path}"
    now = time.monotonic()
    hit = _SIG_CACHE.get(key)
    if hit is not None and now - hit[2] < _SIG_STAT_TTL:
        return hit[1]
    try:
        mtime = (workspace / str(lean_path)).stat().st_mtime
    except OSError:
        return None
    if hit is not None and hit[0] == mtime:
        _SIG_CACHE[key] = (mtime, hit[1], now)
        return hit[1]
    from ...agent.context import goal_display_signature
    sig: "str | None" = goal_display_signature(
        workspace, slug, lean_path, statement)
    if (not sig or sig == str(statement or "")
            or ":= @" in sig or " : " not in sig):
        sig = None
    _SIG_CACHE[key] = (mtime, sig, now)
    return sig


#: How much of a charter a display surface carries inline. The whole
#: claim lives in the group's own read; a lane or a chip needs the
#: subject, not the paragraph.
_CHARTER_SNIP = 240


def _programme_title(body: str) -> "str | None":
    """The Programme's own `# Title` line — what the argument calls
    itself. Falls back to the first prose line for a body that opens
    without one; None when there is nothing to read."""
    for raw in body.splitlines():
        line = raw.strip()
        if line == "":
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        return line[:160] or None
    return None


def _charter_snippet(charter: str) -> str:
    one = " ".join(str(charter or "").split())
    return one[:_CHARTER_SNIP].rstrip() + "…" if len(one) > _CHARTER_SNIP \
        else one


def group_card(conn: sqlite3.Connection, group_id: int) -> "dict | None":
    """The display identity of one discussion group (v35).

    A group is one charter, one Programme, one strategist/adversary
    loop. The TOP group is the problem itself facing a human — its
    charter is the problem's goal (v40), and surfaces must not dress
    it up as a delegated burden: with no sub-groups anywhere, every
    display reads exactly as it did before groups existed.
    """
    try:
        r = conn.execute(
            "SELECT id, problem, parent_group_id, charter, status,"
            " anchor_goal_id, created_at FROM groups WHERE id = ?",
            (int(group_id),)).fetchone()
    except sqlite3.OperationalError:
        return None  # pre-v35 DB
    if r is None:
        return None
    return {
        "id": int(r["id"]),
        "problem": str(r["problem"]),
        "parent_id": (int(r["parent_group_id"])
                      if r["parent_group_id"] is not None else None),
        "is_top": r["parent_group_id"] is None,
        "charter": _charter_snippet(r["charter"]),
        "status": str(r["status"]),
        "anchor_goal_id": (int(r["anchor_goal_id"])
                           if r["anchor_goal_id"] is not None else None),
        "created_at": str(r["created_at"]),
    }


def _top_group_id(conn: sqlite3.Connection, problem: str) -> "int | None":
    """The problem's human-facing group — the one whose Programme and
    revision numbering a problem-level read means."""
    try:
        r = conn.execute(
            "SELECT id FROM groups WHERE problem = ?"
            " AND parent_group_id IS NULL", (problem,)).fetchone()
    except sqlite3.OperationalError:
        return None  # pre-v35 DB: revisions are problem-wide, as before
    return int(r["id"]) if r is not None else None


#: bricks listed per delivered group — the block names what a finished
#: group handed up; beyond this it stops being a list and becomes a
#: file, and the count still tells the truth.
_BRICKS_SHOWN = 40


def _group_lineage(conn: sqlite3.Connection, problem: str,
                   card: dict) -> dict:
    """Where a group sits in the ARGUMENT, not just in the tree.

    `opened_at_rev` is the revision of the parent whose batch delegated
    this claim — the one fact that ties the document to the tree: a
    reader of rev 6 can see that rev 2 and rev 3 each handed a burden
    out and whether it came back. `rev` is the group's OWN chain (every
    group numbers from 1). `bricks` are the goals its strategist
    commissioned — which survives delivery, unlike subtree ownership
    (a delivered group's goals fold into its parent's).
    """
    gid = int(card["id"])
    card["opened_at_rev"] = None
    if card.get("parent_id") is not None:
        row = conn.execute(
            "SELECT r.rev AS rev FROM groups g"
            " JOIN strategist_decisions d ON d.id = g.opened_by"
            " JOIN programme_revisions r ON r.batch_id = d.batch_id"
            "  AND r.problem = d.problem AND r.group_id = d.group_id"
            " WHERE g.id = ? LIMIT 1", (gid,)).fetchone()
        if row is not None:
            card["opened_at_rev"] = int(row["rev"])
    card["rev"] = _programme_rev(conn, problem, gid)
    # A group NAMES itself in its Programme's title line; the charter
    # is the reason it was handed the burden, which is a paragraph and
    # a poor label (owner, 2026-08-07). The charter still travels — as
    # a block inside the group's own read.
    card["title"] = None
    if card["rev"] is not None:
        row = conn.execute(
            "SELECT body FROM programme_revisions"
            " WHERE problem = ? AND group_id = ? AND status = 'passed'"
            " ORDER BY rev DESC LIMIT 1", (problem, gid)).fetchone()
        if row is not None:
            card["title"] = _programme_title(str(row["body"] or ""))
    bricks = conn.execute(
        "SELECT g.slug AS slug, g.id AS id, g.status AS status"
        "  FROM strategist_decisions d JOIN goals g"
        "    ON g.id = d.produced_goal_id"
        " WHERE d.problem = ? AND d.group_id = ?"
        "   AND d.produced_goal_id IS NOT NULL"
        " ORDER BY d.id", (problem, gid)).fetchall()
    proved = [{"id": int(b["id"]), "slug": str(b["slug"])}
              for b in bricks if str(b["status"]) == "proved"]
    card["bricks"] = len(bricks)
    card["bricks_proved"] = len(proved)
    # only a group that has HANDED ITS WORK UP carries the list: that
    # is the reading ("what may I cite now"); a group still arguing is
    # read through its own Programme, not through a brick inventory
    card["delivered_bricks"] = (proved[:_BRICKS_SHOWN]
                                if card["status"] == "delivered" else [])
    return card


def groups_of(conn: sqlite3.Connection, problem: str) -> "list[dict]":
    """Every group in the problem, top first then by age — the tree a
    reader needs to know exists before any of it can be shown, each
    carrying where it came from and what it produced."""
    try:
        rows = conn.execute(
            "SELECT id FROM groups WHERE problem = ?"
            " ORDER BY (parent_group_id IS NULL) DESC, id", (problem,)
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    out = []
    for r in rows:
        card = group_card(conn, int(r["id"]))
        if card is not None:
            out.append(_group_lineage(conn, problem, card))
    return out


def _disproof_links(conn: sqlite3.Connection,
                    problem: str) -> "dict[int, dict]":
    """produced ¬P goal id → {id, slug} of the target P, from
    AttemptDisproof decision rows (the framework's mechanical linkage —
    no schema, no name-pattern guessing). A star that IS a disproof
    must say so wherever it is read: the sky dresses a proved negation
    exactly like ordinary success otherwise."""
    out: dict[int, dict] = {}
    for r in conn.execute(
            "SELECT d.produced_goal_id AS neg, g.id AS tid, g.slug AS slug"
            " FROM strategist_decisions d"
            " JOIN goals g ON g.id = d.target_id"
            " WHERE d.problem = ? AND d.decision_kind = 'AttemptDisproof'"
            " AND d.produced_goal_id IS NOT NULL", (problem,)):
        out[int(r["neg"])] = {"id": int(r["tid"]), "slug": str(r["slug"])}
    return out


def goal_workarea_draft(workspace: Path, slug: str) -> "Path | None":
    """Freshest .lean draft in the workarea serving goal `slug`
    (matched by Context.md's '# Context for goal <slug>' heading —
    only the owning agent's context carries it as a heading, so a
    sibling merely CITING the slug never matches). The Formalizer
    drafts `patch.lean` here and only lands at commit, so this is the
    ONLY place its work exists until then — the run lane and the goal
    panel both read it."""
    marker = f"# Context for goal {slug}"
    best: "Path | None" = None
    best_m = -1.0
    try:
        entries = list((workspace / ".attempts").iterdir())
    except OSError:
        return None
    for d in entries:
        if d.name.startswith("_") or not d.is_dir():
            continue
        try:
            ctx = (d / "Context.md").read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            continue
        if marker not in ctx:
            continue
        try:
            for f in d.glob("*.lean"):
                if f.name.startswith("_"):
                    continue
                mt = f.stat().st_mtime
                if mt > best_m:
                    best_m = mt
                    best = f
        except OSError:
            continue
    return best


def _mtime_or(path: Path, default: float = -1.0) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return default


def _goal_source(conn: sqlite3.Connection, workspace: Path,
                 goal_id: int, slug: str,
                 lean_path: str) -> "tuple[str, str, int | None]":
    """(path, state, strategy_id) — WHICH text the panel should show for
    this goal, and what that text is.

    A node's own file is a `:= by sorry` stub for its whole working
    life: the decomposition lands in the ROUTE's file and the live
    attempt exists only in a workarea. Showing the stub told the reader
    nothing about how the goal was actually split (owner, 2026-08-01).
    Freshest meaningful text wins:

      winning_route — the route that closed it (its scratch IS the proof)
      open_route    — a route still open: how the goal is split right now
      in_flight     — an attempt writing this minute (scratch; may vanish)
      own_file      — no route, no draft: the goal's own file as it stands
    """
    src, state, sid = lean_path, "own_file", None
    row = conn.execute(
        "SELECT id, scratch_path, status FROM strategies"
        " WHERE goal_id = ? AND scratch_path != ''"
        # succeeded first, then the newest live route; a dead route's
        # skeleton is forensics, reachable through its own panel
        "   AND status IN ('succeeded', 'proposed')"
        " ORDER BY (status = 'succeeded') DESC, id DESC LIMIT 1",
        (goal_id,)).fetchone()
    if row is not None and (workspace / str(row["scratch_path"])).is_file():
        src = str(row["scratch_path"])
        sid = int(row["id"])
        state = ("winning_route" if str(row["status"]) == "succeeded"
                 else "open_route")
    draft = goal_workarea_draft(workspace, slug)
    if draft is not None and _mtime_or(draft) > _mtime_or(workspace / src):
        # same rule the run lane uses: while the draft is the fresher
        # text, the draft IS the live view
        try:
            return (draft.relative_to(workspace).as_posix(),
                    "in_flight", sid)
        except ValueError:
            pass
    return src, state, sid


def goal_detail(conn: sqlite3.Connection, problem: str,
                goal_id: int,
                workspace: "Path | None" = None) -> dict | None:
    """Goal drill-down: full row + dead-attempt forensics (most recent
    first, capped). With `workspace`, also the declaration source —
    the proof file minus its import prelude (a node IS its Lean text;
    the panel shows `name : statement := proof` as written), picked by
    `_goal_source` so a working node shows its work, not its stub."""
    g = conn.execute(
        "SELECT * FROM goals WHERE id = ? AND problem = ?",
        (goal_id, problem)).fetchone()
    if g is None:
        return None
    proof_text = None
    src = g["lean_path"]
    source_state, source_strategy_id = "own_file", None
    if workspace is not None:
        src, source_state, source_strategy_id = _goal_source(
            conn, workspace, goal_id, str(g["slug"]), str(g["lean_path"]))
        try:
            text = (workspace / str(src)).read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        # drop import lines wherever they sit (a header comment may
        # precede them and is worth keeping — it is the agent's own
        # narration); collapse the blank run they leave behind
        kept = [ln for ln in text.splitlines()
                if not ln.startswith("import ")]
        out_lines: list[str] = []
        for ln in kept:
            if not ln.strip() and out_lines and not out_lines[-1].strip():
                continue
            out_lines.append(ln)
        proof_text = "\n".join(out_lines).strip()[:40000] or None
    dead = []
    for r in conn.execute(
            "SELECT id, pipeline_id, failure_reason, failure_detail,"
            " proposal_md, ts FROM dead_attempts"
            " WHERE target_kind = 'Goal' AND target_id = ?"
            " ORDER BY id DESC LIMIT 50", (goal_id,)):
        dead.append({
            "id": int(r["id"]),
            "pipeline_id": str(r["pipeline_id"]),
            "failure_reason": str(r["failure_reason"]),
            "failure_detail": r["failure_detail"],
            "proposal_md": r["proposal_md"],
            "ts": str(r["ts"]),
        })
    # subgoal names per route (owner, 2026-07-11): seven rows of
    # '1 subgoal' were indistinguishable — the panel names each route's
    # children and lights their stars on hover
    subgoals_of: dict[int, list[dict]] = {}
    for r in conn.execute(
            "SELECT ss.strategy_id AS sid, g2.id AS gid, g2.slug AS slug,"
            f" {_link_kind_expr(conn)} AS link_kind"
            " FROM strategy_subgoals ss"
            " JOIN strategies s ON s.id = ss.strategy_id"
            " JOIN goals g2 ON g2.id = ss.subgoal_id"
            " WHERE s.goal_id = ? ORDER BY g2.id", (goal_id,)):
        # a route's inputs include lemmas it did not create; the panel
        # lists them all and says which is which, rather than claiming
        # the route decomposed into eight things it merely reuses
        subgoals_of.setdefault(int(r["sid"]), []).append(
            {"id": int(r["gid"]), "slug": str(r["slug"]),
             "reused": str(r["link_kind"]) == "cited"})
    strategies = [{
        "id": int(r["id"]),
        "status": str(r["status"]),
        "created_by": str(r["created_by"]),
        "subgoal_count": int(r["n"]),
        "subgoals": subgoals_of.get(int(r["id"]), []),
    } for r in conn.execute(
        "SELECT s.id, s.status, s.created_by,"
        " (SELECT COUNT(*) FROM strategy_subgoals ss"
        "  WHERE ss.strategy_id = s.id) AS n"
        " FROM strategies s WHERE s.goal_id = ? ORDER BY s.id DESC",
        (goal_id,))]
    return {
        "id": int(g["id"]),
        "slug": str(g["slug"]),
        "status": str(g["status"]),
        "kind": str(g["kind"]),
        "origin": str(g["origin"]),
        "statement": str(g["statement"]),
        "lean_path": str(g["lean_path"]),
        "depth": int(g["depth"]),
        "detached": bool(g["detached"]),
        "alias_target_id": g["alias_target_id"],
        "is_deliverable": bool(g["is_deliverable"]),
        "created_at": str(g["created_at"]),
        "disproof_of": _disproof_links(conn, problem).get(int(g["id"])),
        "proof_text": proof_text,
        # the file the source above was actually read from — the panel's
        # path label must name what it shows
        "source_path": str(src),
        # ...and WHAT it is: a proof, a live decomposition, an attempt
        # in flight, or the node's own file. The reader cannot tell a
        # route skeleton from a landed proof by looking at it.
        "source_state": source_state,
        "source_strategy_id": source_strategy_id,
        "dead_attempts": dead,
        "strategies": strategies,
    }


def strategy_detail(conn: sqlite3.Connection, problem: str,
                    strategy_id: int) -> dict | None:
    """Strategy drill-down: the decomposition's own record —
    proposal_md (the agent's reasoning), status, subgoals."""
    s = conn.execute(
        "SELECT s.id, s.goal_id, s.status, s.proposal_md, s.created_by,"
        " s.created_at, g.problem, g.slug AS goal_slug"
        " FROM strategies s JOIN goals g ON g.id = s.goal_id"
        " WHERE s.id = ? AND g.problem = ?",
        (strategy_id, problem)).fetchone()
    if s is None:
        return None
    subgoals = [{
        "id": int(r["id"]),
        "slug": str(r["slug"]),
        "status": str(r["status"]),
        "position": int(r["position"]),
        "reused": str(r["link_kind"]) == "cited",
    } for r in conn.execute(
        "SELECT g.id, g.slug, g.status, ss.position,"
        f" {_link_kind_expr(conn)} AS link_kind"
        " FROM strategy_subgoals ss JOIN goals g ON g.id = ss.subgoal_id"
        " WHERE ss.strategy_id = ? ORDER BY ss.position",
        (strategy_id,))]
    dead = []
    for r in conn.execute(
            "SELECT id, pipeline_id, failure_reason, failure_detail, ts"
            " FROM dead_attempts"
            " WHERE target_kind = 'Strategy' AND target_id = ?"
            " ORDER BY id DESC LIMIT 20", (strategy_id,)):
        dead.append({
            "id": int(r["id"]),
            "pipeline_id": str(r["pipeline_id"]),
            "failure_reason": str(r["failure_reason"]),
            "failure_detail": r["failure_detail"],
            "ts": str(r["ts"]),
        })
    return {
        "id": int(s["id"]),
        "goal_id": int(s["goal_id"]),
        "goal_slug": str(s["goal_slug"]),
        "status": str(s["status"]),
        "proposal_md": str(s["proposal_md"] or ""),
        "created_by": str(s["created_by"]),
        "created_at": str(s["created_at"]),
        "subgoals": subgoals,
        "dead_attempts": dead,
    }


def review(conn: sqlite3.Connection, problem: str) -> dict | None:
    """Ingest-time review snapshot (charter: GET never touches the
    gateway). None when the problem has no stored snapshot yet."""
    from ...quality import review as _review
    loaded = _review.load_review_snapshot(conn, problem)
    if loaded is None:
        return None
    data, stored_at = loaded
    return {"stored_at": stored_at, **data}


def signoff_with_seal(conn: sqlite3.Connection,
                      problem: str) -> "dict | None":
    """The sign-off signature record (v27) + `seal_ok`: sha256 of the
    CURRENTLY stored review snapshot compared against the sha sealed at
    signing. False = the snapshot changed after the human signed (a
    refresh recomputed different content) — the reader must see that,
    not a seal that silently stopped meaning anything. None = never
    signed / revoked / predates signatures."""
    import hashlib
    rec = db.get_ingest_signoff(conn, problem)
    if rec is None:
        return None
    snap = db.get_review_snapshot(conn, problem)
    current_sha = (hashlib.sha256(snap[0].encode("utf-8")).hexdigest()
                   if snap else None)
    return {**rec, "seal_ok": (rec.get("snapshot_sha") is not None
                               and rec.get("snapshot_sha") == current_sha)}


def library(conn: sqlite3.Connection) -> dict:
    """Bridged Library decls, grouped per source problem."""
    out = []
    for problem, rows in db.bridged_library_index(conn).items():
        out.append({
            "problem": problem,
            "decls": [{
                "slug": str(r["slug"]),
                "name": r["target_name"],
                "file": r["target_file"],
                "signature": r["signature"],
                "decl_kind": r["decl_kind"],
                "lifecycle": str(r["lifecycle"]),
            } for r in rows],
        })
    return {"problems": out}
