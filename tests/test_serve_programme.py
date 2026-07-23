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
    assert r.json() == {"current": None, "history": []}
    # and the detail advertises no tab
    assert c.get("/api/problems/Test.rm").json()["programme_rev"] is None


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
