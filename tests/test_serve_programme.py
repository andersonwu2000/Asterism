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
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()))
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
                        "group_id": None, "groups": []}
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
