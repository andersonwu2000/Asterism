"""The console's on-demand read of one revision's judge verdict.

Guards the two things the 2026-08-29 judge change made readable and the
one shape it changed:

  * a criterion takes a LIST — one bullet per objection — and a judge
    that fires three defects under one criterion must show three, not
    the first (owner design, 2026-08-28);
  * a REJECTED revision keeps its verdict (survey knife 0; the column
    used to be hard-coded NULL, which destroyed 89 final verdicts and
    left the row a reader most wants to open with nothing to open);
  * the `_judge` stamp lands in four columns and rides to the console.

The reading itself goes through `adversary.split_criterion`, so this
also pins that the serve layer never grew its own copy of it.
"""
from __future__ import annotations

import json
import sqlite3

from Tooling.serve import data
from Tooling.serve.data.timeline import _programme_events


def _row(conn: sqlite3.Connection, *, problem: str = "p", rev: int = 1,
         status: str = "passed", verdict: "dict | None" = None,
         rounds: int = 0, judge: "dict | None" = None,
         discard_channel: "str | None" = None) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO problems (name, created_at)"
        " VALUES (?, '2026-08-29T00:00:00+00:00')", (problem,))
    cur = conn.execute(
        "INSERT INTO programme_revisions"
        " (problem, rev, body, status, verdict, dialogue, rounds,"
        "  created_at, discard_channel,"
        "  judge_model, judge_provider, judge_effort, rubric_sha)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (problem, rev, "# Title\n\nbody", status,
         json.dumps(verdict) if verdict is not None else None,
         "[]", rounds, "2026-08-29T00:00:00+00:00", discard_channel,
         (judge or {}).get("model"), (judge or {}).get("provider"),
         (judge or {}).get("effort"), (judge or {}).get("rubric_sha")))
    return int(cur.lastrowid)


PASS = {
    "verdict": "pass",
    "criticisms": [],
    "reservations": ["the bound is stated loosely"],
    "criteria": {
        "1": ["clear: the batch is work the charter needs"],
        "2": ["clear - AHEAD 7 closes the MAIN claim"],
        "3": ["clear: every step is complete"],
        "4": ["clear: every step of the Proof is complete"],
    },
}

REBUT = {
    "verdict": "rebut",
    "criticisms": ["c1", "c2", "c3"],
    "reservations": ["a caveat"],
    "criteria": {
        # THE list schema: three defects under one criterion, all fired
        # this round instead of one per round
        "3": ["fired: step 4 has a hole",
              "fired: step 7 assumes what it proves",
              "fired: the bound is off by one"],
        "1": ["clear: the work is needed"],
        "2": ["clear: the entry is named"],
        "4": ["clear: backed"],
    },
}


def test_a_fired_criterion_shows_every_bullet(conn: sqlite3.Connection):
    rid = _row(conn, status="rejected", verdict=REBUT, rounds=10,
               discard_channel="strategist_proposal_rejected")
    v = data.programme_verdict(conn, "p", rid)
    assert v is not None
    by = {c["key"]: c for c in v["criteria"]}
    assert by["3"]["state"] == "fired"
    assert by["3"]["bullets"] == [
        "step 4 has a hole",
        "step 7 assumes what it proves",
        "the bound is off by one",
    ], "a criterion is a list now — showing the first bullet drops the rest"
    assert by["1"]["state"] == "clear"
    assert by["1"]["bullets"] == ["the work is needed"], (
        "the head word is stripped: the state is already on the row, and "
        "drawing it twice is what the visual language forbids")


def test_a_killed_revision_still_says_why(conn: sqlite3.Connection):
    """Knife 0. The row used to carry verdict=NULL."""
    rid = _row(conn, status="rejected", verdict=REBUT, rounds=10,
               discard_channel="strategist_proposal_rejected")
    v = data.programme_verdict(conn, "p", rid)
    assert v["status"] == "rejected"
    assert v["ruling"] == "rebut"
    assert v["criticisms"] == ["c1", "c2", "c3"]
    assert v["discard_channel"] == "strategist_proposal_rejected"
    assert any(c["state"] == "fired" for c in v["criteria"])


def test_the_rubric_names_and_orders_the_criteria(conn: sqlite3.Connection):
    """The names come from the prompt, never a third copy of the rubric.
    Value and Reachability swapped places on 2026-08-13, and the owner
    revises the list again whenever the rubric changes — so the
    expectation is READ from the rubric here too. Writing the names down
    in the test would only pin whichever rubric was current the day it
    was written, and the page would keep rendering yesterday's labels
    with the test green."""
    from Tooling.pipeline import adversary
    names = adversary.criteria_names()
    assert names, "the rubric's names no longer parse out of the prompt"
    rid = _row(conn, verdict=REBUT)
    v = data.programme_verdict(conn, "p", rid)
    assert ([c["key"] for c in v["criteria"]]
            == list(adversary.CRITERIA_KEYS)), (
        "the JSON put 3 first; the page follows the rubric's order")
    assert [c["name"] for c in v["criteria"]] == [
        names[k] for k in adversary.CRITERIA_KEYS], (
        "the page must label a criterion with the rubric's own name")


def test_the_seat_rides_and_says_nothing_when_unrecorded(
        conn: sqlite3.Connection):
    stamp = {"model": "gpt-5.6-sol", "provider": "codex",
             "effort": "high", "rubric_sha": "074ab0023e569250"}
    rid = _row(conn, verdict=PASS, judge=stamp)
    assert data.programme_verdict(conn, "p", rid)["judge"] == stamp
    # every verdict written before 2026-08-28 has no stamp: say so
    # rather than inventing a seat
    old = _row(conn, rev=2, verdict=PASS)
    assert data.programme_verdict(conn, "p", old)["judge"] is None


def test_the_legacy_string_criterion_still_reads(conn: sqlite3.Connection):
    """A bare string is the pre-2026-08-28 one-bullet form and half the
    archive is written that way."""
    rid = _row(conn, verdict={
        "verdict": "rebut", "criticisms": [], "reservations": [],
        "criteria": {"1": "fired: the old shape", "2": "clear: fine",
                     "3": "clear: fine", "4": "clear: fine"}})
    by = {c["key"]: c
          for c in data.programme_verdict(conn, "p", rid)["criteria"]}
    assert by["1"]["state"] == "fired"
    assert by["1"]["bullets"] == ["the old shape"]


def test_a_verdict_the_parser_would_refuse_is_still_readable(
        conn: sqlite3.Connection):
    """A bare `clear` is refused as of knife 1 — and a refused verdict is
    exactly the one a reader opens the row to look at."""
    rid = _row(conn, verdict={
        "verdict": "pass", "criteria": {"1": ["clear"], "2": ["clear"],
                                        "3": ["clear"],
                                        "4": ["clear"]}})
    v = data.programme_verdict(conn, "p", rid)
    assert [c["state"] for c in v["criteria"]] == ["clear"] * 4
    assert all(c["bullets"] == [] for c in v["criteria"]), (
        "a bare clear has nothing to say — the page shows the silence")


def test_a_missing_or_foreign_revision_is_nothing(conn: sqlite3.Connection):
    rid = _row(conn, verdict=PASS)
    assert data.programme_verdict(conn, "p", 999999) is None
    assert data.programme_verdict(conn, "other", rid) is None


def test_the_row_id_is_the_handle_the_rev_cannot_be(
        conn: sqlite3.Connection):
    """`rev` names several rows — a rejected proposal and the revision
    that later takes its number (union_closed group 382 has seven rev 1
    rows), so the Timeline event carries the row id."""
    a = _row(conn, rev=1, status="rejected", verdict=REBUT)
    b = _row(conn, rev=1, status="passed", verdict=PASS)
    ids = {e["rev"]: [] for e in _programme_events(conn, "p")}
    for e in _programme_events(conn, "p"):
        ids[e["rev"]].append(e["id"])
    assert sorted(ids[1]) == sorted([a, b])
    assert data.programme_verdict(conn, "p", a)["status"] == "rejected"
    assert data.programme_verdict(conn, "p", b)["status"] == "passed"
