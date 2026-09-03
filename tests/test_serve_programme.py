"""GET /api/problems/{p}/programme contract tests (research mode read
surface). Same charter as the other serve tests: tmp workspace, no
spawns, read-only."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.serve.app import create_app
from Tooling.state import db
from Tooling.state import programme as prog


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


def _open_db(workspace: Path) -> sqlite3.Connection:
    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)
    return conn


def _add_problem(conn: sqlite3.Connection, name: str = "Test.rm") -> None:
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)",
        (name, db.now()))
    conn.commit()


_BODY_V1 = ("# Prove the toy bound\n\n## Argument\nA.\n\n"
            "## Proof\nT.\n\n## Roadmap\nR.")
_BODY_V2 = ("# Prove the toy bound, sharpened\n\n## Argument\nA2.\n\n"
            "## Proof\nT2.\n\n## Roadmap\nR2.")


def test_programme_unknown_problem_404(workspace: Path) -> None:
    _open_db(workspace).close()
    r = TestClient(create_app(workspace)).get(
        "/api/problems/No.such/programme")
    assert r.status_code == 404


def test_programme_empty_before_bootstrap(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn)
    conn.close()
    c = TestClient(create_app(workspace))
    r = c.get("/api/problems/Test.rm/programme")
    assert r.status_code == 200
    assert r.json() == {"current": None, "history": [],
                        "group_id": None, "charter": None, "groups": []}
    # and the detail advertises no tab
    assert c.get("/api/problems/Test.rm").json()["programme_rev"] is None


def test_programme_reads_one_group_never_interleaves(
        workspace: Path) -> None:
    """v35 — every discussion group owns a revision chain numbered from
    1. A problem-wide read would interleave them and call the max of
    two unrelated numberings "current": the page would show one
    argument's rev 2 as the successor of another's rev 1. The problem
    read means the TOP group; a sub-group is reachable by id, and only
    within its own problem."""
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn)
    _add_problem(conn, "Test.other")
    top = _groups.ensure_top_group(conn, "Test.rm")
    sub = _groups.open_group(conn, problem="Test.rm", parent_group_id=top,
                             charter="settle the sub-claim")
    other_top = _groups.ensure_top_group(conn, "Test.other")
    prog.record_pass(conn, "Test.rm", _BODY_V1, {"reservations": []}, [],
                     rounds=0, batch_id="b1", group_id=top)
    prog.record_pass(conn, "Test.rm", _BODY_V2, {"reservations": []}, [],
                     rounds=0, batch_id="b2", group_id=top)
    # the sub-group's own chain restarts at 1 and argues something else
    prog.record_pass(conn, "Test.rm", "# Sub\n\n## Argument\nS.",
                     {"reservations": ["sub caveat"]}, [], rounds=1,
                     batch_id="b3", group_id=sub)
    conn.commit()
    conn.close()
    c = TestClient(create_app(workspace))

    top_read = c.get("/api/problems/Test.rm/programme").json()
    assert top_read["group_id"] == top
    assert top_read["current"]["rev"] == 2
    assert top_read["current"]["body"] == _BODY_V2
    assert [h["rev"] for h in top_read["history"]] == [2, 1]  # no sub rev
    # the tree is named so a reader knows the other argument exists
    assert [(g["id"], g["is_top"], g["charter"]) for g in top_read["groups"]] \
        == [(top, True, ""), (sub, False, "settle the sub-claim")]

    sub_read = c.get(f"/api/problems/Test.rm/programme?group={sub}").json()
    assert sub_read["current"]["rev"] == 1
    assert sub_read["current"]["reservations"] == ["sub caveat"]
    assert [h["rev"] for h in sub_read["history"]] == [1]

    # the problem's own number is the top group's, never a sub-group's
    detail = c.get("/api/problems/Test.rm").json()
    assert detail["programme_rev"] == 2
    assert [e["rev"] for e in detail["programme_events"]] == [2, 1]

    # another problem's group is a 404, not somebody else's argument
    assert c.get(f"/api/problems/Test.rm/programme?group={other_top}"
                 ).status_code == 404
    assert c.get("/api/problems/Test.rm/programme?group=99999"
                 ).status_code == 404


def test_group_cards_carry_their_lineage(workspace: Path) -> None:
    """A group card says where in the ARGUMENT it was handed out
    (`opened_at_rev` — the parent revision whose batch delegated it),
    what its own chain has reached, and what it built. Subtree
    ownership folds into the parent when a group delivers; the
    commissioned-brick record does not, which is why the display reads
    that instead (owner, 2026-08-07)."""
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn)
    top = _groups.ensure_top_group(conn, "Test.rm")
    prog.record_pass(conn, "Test.rm", _BODY_V1, {"reservations": []}, [],
                     rounds=0, batch_id="b1", group_id=top)
    prog.record_pass(conn, "Test.rm", _BODY_V2, {"reservations": []}, [],
                     rounds=0, batch_id="b2", group_id=top)
    sub = _groups.open_group(conn, problem="Test.rm", parent_group_id=top,
                             charter="# Charter: settle the sub-claim")
    # the Delegate row is what ties the group to the revision: its
    # batch is the one rev 2 authorised
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, produced_group_id,"
        " batch_id, created_at, updated_at) VALUES (?, 0, 'routine',"
        " 'Delegate', ?, ?, 'b2', ?, ?)",
        ("Test.rm", top, sub, db.now(), db.now()))
    conn.execute("UPDATE groups SET opened_by = ? WHERE id = ?",
                 (int(cur.lastrowid), sub))
    # two commissioned bricks, one proved
    for slug, status in (("brick_a", "proved"), ("brick_b", "open")):
        gid = db.insert_goal(conn, problem="Test.rm", slug=slug,
                             lean_path=f"Problems/Test.rm/proofs/{slug}.lean",
                             statement="True", origin="forward")
        if status == "proved":
            conn.execute("UPDATE goals SET status='proved' WHERE id=?", (gid,))
        conn.execute(
            "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
            " trigger_kind, decision_kind, group_id, produced_goal_id,"
            " created_at, updated_at) VALUES (?, 0, 'routine', 'Inject',"
            " ?, ?, ?, ?)", ("Test.rm", sub, gid, db.now(), db.now()))
    conn.commit()
    conn.close()
    c = TestClient(create_app(workspace))
    cards = {g["id"]: g for g in
             c.get("/api/problems/Test.rm/programme").json()["groups"]}

    assert cards[top]["opened_at_rev"] is None   # nobody handed it out
    assert cards[top]["rev"] == 2
    assert cards[sub]["opened_at_rev"] == 2      # out of the parent's rev 2
    assert cards[sub]["rev"] is None             # its own chain is empty
    assert cards[sub]["bricks"] == 2
    assert cards[sub]["bricks_proved"] == 1
    # the inventory of what came home is for a group that HAS come home
    assert cards[sub]["delivered_bricks"] == []
    conn = _open_db(workspace)
    _groups.set_status(conn, sub, "delivered", event="ingest")
    conn.commit()
    conn.close()
    cards = {g["id"]: g for g in
             c.get("/api/problems/Test.rm/programme").json()["groups"]}
    assert [b["slug"] for b in cards[sub]["delivered_bricks"]] == ["brick_a"]


def test_programme_chain_and_rejections(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn)
    prog.record_pass(conn, "Test.rm", _BODY_V1,
                     {"reservations": []}, [], rounds=0, batch_id="b1")
    prog.record_rejection(conn, "Test.rm", "# Bad\n\n## Argument\nx",
                          [{"role": "adversary", "text": "no"}], rounds=3)
    prog.record_pass(conn, "Test.rm", _BODY_V2,
                     {"reservations": ["the bound may be loose"]},
                     [{"role": "adversary", "text": "ok"}],
                     rounds=1, batch_id="b2")
    conn.commit()
    conn.close()

    c = TestClient(create_app(workspace))
    body = c.get("/api/problems/Test.rm/programme").json()
    cur = body["current"]
    assert cur["rev"] == 2
    assert cur["rounds"] == 1
    assert cur["reservations"] == ["the bound may be loose"]
    assert cur["body"].startswith("# Prove the toy bound, sharpened")
    # history: newest first, both statuses, no bodies/dialogue
    assert [(h["rev"], h["status"]) for h in body["history"]] == [
        (2, "passed"), (2, "rejected"), (1, "passed")]
    assert all("body" not in h and "dialogue" not in h
               for h in body["history"])
    assert c.get("/api/problems/Test.rm").json()["programme_rev"] == 2


def test_programme_verdict_json_garbage_is_tolerated(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn)
    conn.execute(
        "INSERT INTO programme_revisions (problem, rev, body, status,"
        " verdict, dialogue, rounds, batch_id, created_at)"
        " VALUES ('Test.rm', 1, ?, 'passed', 'not json', ?, 0, NULL, ?)",
        (_BODY_V1, json.dumps([]), db.now()))
    conn.commit()
    conn.close()
    body = TestClient(create_app(workspace)).get(
        "/api/problems/Test.rm/programme").json()
    assert body["current"]["reservations"] == []


def test_problem_detail_carries_programme_events(workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn)
    prog.record_rejection(conn, "Test.rm", "# Bad\n\n## Argument\nx",
                          [], rounds=4)
    prog.record_pass(conn, "Test.rm", _BODY_V1, {"reservations": []},
                     [], rounds=1, batch_id="b1")
    conn.commit()
    conn.close()
    body = TestClient(create_app(workspace)).get(
        "/api/problems/Test.rm").json()
    ev = body["programme_events"]
    assert [(e["rev"], e["status"], e["rounds"]) for e in ev] == [
        (1, "passed", 1), (1, "rejected", 4)]


# ---------------------------------------------------------------------
# the revision history and one revision's debate (HID §1.4-2, third
# bullet: "提供 Programme 定案歷史和各定案下的辯論歷史")
# ---------------------------------------------------------------------


_JUDGE = {"model": "m1", "provider": "prov", "effort": "high",
          "rubric_sha": "abc"}


def _round(n: int, proposal: str, *criticisms: str) -> dict:
    """One stored dialogue turn — the judge's, carrying the body it was
    fired at (`pipeline/strategist/wake.py`)."""
    return {"round": n, "role": "adversary", "criticisms": list(criticisms),
            "proposal": proposal,
            "verdict": {"verdict": "revise", "criticisms": list(criticisms),
                        "reservations": [],
                        "criteria": {"1": ["fired: the batch drifts"]}}}


def test_programme_revision_list_is_the_chain_with_its_provenance(
        workspace: Path) -> None:
    """The Groups screen shows the decided history under the tree, so
    one row must carry everything the list is read by: which rev, how it
    ended, how many rounds it survived, when, which seat judged it, and
    — for a discard — why it was dropped."""
    from Tooling.state import groups as _groups
    conn = _open_db(workspace)
    _add_problem(conn)
    top = _groups.ensure_top_group(conn, "Test.rm")
    sub = _groups.open_group(conn, problem="Test.rm", parent_group_id=top,
                             charter="a handed-out claim")
    prog.record_pass(conn, "Test.rm", _BODY_V1,
                     {"reservations": [], "_judge": _JUDGE}, [], rounds=0,
                     batch_id="b1", group_id=top)
    prog.record_rejection(conn, "Test.rm", "# Bad", [], rounds=3,
                          discard_reason="adversary rebuttal",
                          group_id=top, discard_channel="adversarial")
    prog.record_pass(conn, "Test.rm", "# Sub argument", {"reservations": []},
                     [], rounds=2, batch_id="b2", group_id=sub)
    conn.commit()
    conn.close()

    c = TestClient(create_app(workspace))
    r = c.get("/api/problems/Test.rm/programme/revisions")
    assert r.status_code == 200, r.text
    rows = r.json()["revisions"]
    # newest first, the TOP group's chain — a sub-group's argument is
    # not this one's history (v35: chains never interleave)
    assert [(x["rev"], x["status"], x["rounds"]) for x in rows] == [
        (2, "rejected", 3), (1, "passed", 0)]
    assert all(x["group_id"] == top for x in rows)
    assert rows[0]["discard_reason"] == "adversary rebuttal"
    assert rows[1]["judge"] == _JUDGE
    assert rows[0]["judge"] is None      # never judged — not invented
    assert all("body" not in x and "dialogue" not in x for x in rows)
    # …and the sub-group's chain is reachable by id
    subrows = c.get(
        f"/api/problems/Test.rm/programme/revisions?group={sub}").json()
    assert [(x["rev"], x["status"]) for x in subrows["revisions"]] == [
        (1, "passed")]
    assert c.get("/api/problems/No.such/programme/revisions"
                 ).status_code == 404


def test_one_revision_carries_its_body_debate_and_verdict(
        workspace: Path) -> None:
    """Opening a revision shows what was decided AND the argument that
    got there: the rounds alternate strategist (the body it put on the
    table) and adversary (what it fired back), and the per-criterion
    verdict closes it."""
    conn = _open_db(workspace)
    _add_problem(conn)
    dialogue = [_round(1, "# Draft one", "the batch drifts from the charter"),
                _round(2, "# Draft two", "step 3 is still not closed")]
    prog.record_pass(
        conn, "Test.rm", _BODY_V2,
        {"verdict": "pass", "criticisms": [], "reservations": ["loose"],
         "criteria": {"1": ["clear: it is what the charter needs"]},
         "_judge": _JUDGE},
        dialogue, rounds=2, batch_id="b1")
    rev_id = int(conn.execute(
        "SELECT id FROM programme_revisions").fetchone()[0])
    conn.commit()
    conn.close()

    c = TestClient(create_app(workspace))
    r = c.get(f"/api/problems/Test.rm/programme/revisions/{rev_id}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["rev"] == 1 and d["status"] == "passed"
    assert d["body"].startswith("# Prove the toy bound, sharpened")
    assert [x["round"] for x in d["dialogue"]] == [1, 2]
    assert d["dialogue"][0]["proposal"] == "# Draft one"
    assert d["dialogue"][0]["criticisms"] == [
        "the batch drifts from the charter"]
    assert d["dialogue"][0]["ruling"] == "revise"
    assert d["dialogue"][0]["criteria"][0]["state"] == "fired"
    assert d["dialogue"][0]["criteria"][0]["bullets"] == ["the batch drifts"]
    # the closing verdict is the shape the existing endpoint already
    # answers with — one reading of a verdict, not two
    assert d["verdict"] == c.get(
        f"/api/problems/Test.rm/programme/verdict/{rev_id}").json()
    assert c.get("/api/problems/Test.rm/programme/revisions/9999"
                 ).status_code == 404


def test_a_revision_of_another_problem_is_not_this_ones(
        workspace: Path) -> None:
    conn = _open_db(workspace)
    _add_problem(conn)
    _add_problem(conn, "Test.other")
    prog.record_pass(conn, "Test.other", _BODY_V1, {"reservations": []},
                     [], rounds=0, batch_id="b1")
    rev_id = int(conn.execute(
        "SELECT id FROM programme_revisions").fetchone()[0])
    conn.commit()
    conn.close()
    assert TestClient(create_app(workspace)).get(
        f"/api/problems/Test.rm/programme/revisions/{rev_id}"
    ).status_code == 404
