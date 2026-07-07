"""GET /api/run contract tests — the mission-control read.

Same charter as test_serve_api: tmp workspace, no toolchain spawn,
read surface never writes. Worker lanes are engine-liveness claims
(live pid gate), file tails come from the real lean path (spawn writes
go through to real), and the idle console keeps telling the last run's
story via last_exit.scope.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Tooling.serve.app import create_app
from Tooling.state import db


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    return tmp_path


def _open_db(workspace: Path) -> sqlite3.Connection:
    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)
    return conn


def _client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


def _add_problem(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, ?, ?)",
        (name, f"Problems/{name}/Manifest.md", db.now()))
    conn.commit()


def _fake_daemon(monkeypatch, *, running: bool = True, pid: int = 4321,
                 scope: "str | None" = None,
                 last_exit: "dict | None" = None) -> None:
    import Tooling.core.cli as _cli

    def fake_status(workspace):  # noqa: ANN001
        return {"running": running, "pid": pid if running else None,
                "scope": scope if running else None,
                "started_at": db.now() if running else None,
                "stopping": False, "in_flight_leases": 0,
                "last_exit": last_exit}
    monkeypatch.setattr(_cli, "daemon_status", fake_status)


def test_run_fresh_workspace_is_quiet(workspace: Path) -> None:
    r = _client(workspace).get("/api/run")
    assert r.status_code == 200
    body = r.json()
    assert body["workers"] == []
    assert body["goals"] is None


def test_run_live_lanes_carry_statement_and_file_tail(
        workspace: Path, monkeypatch) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    gid = db.insert_goal(conn, problem="p", slug="lemma_a",
                         lean_path="Problems/p/proofs/L_lemma_a.lean",
                         statement="a = a", origin="root")
    # a live lease owned by the daemon pid + one residue lease from a
    # dead pid — only the live one becomes a lane
    db.enqueue(conn, kind="Builder", target_id=str(gid),
               target_kind="Goal", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 4321, leased_at = ?"
                 " WHERE target_id = ?", (db.now(), str(gid)))
    db.enqueue(conn, kind="Builder", target_id="999",
               target_kind="Goal", problem="p")
    conn.execute("UPDATE queue SET owner_pid = 111, leased_at = ?"
                 " WHERE target_id = '999'", (db.now(),))
    conn.commit()
    conn.close()
    proof = workspace / "Problems" / "p" / "proofs" / "L_lemma_a.lean"
    proof.parent.mkdir(parents=True)
    proof.write_text("import Mathlib\n\ntheorem lemma_a : a = a := by\n  rfl\n",
                     encoding="utf-8")

    _fake_daemon(monkeypatch, scope="p")
    body = _client(workspace).get("/api/run").json()
    assert body["problem"] == "p"
    assert body["goals"]["total"] == 1
    assert len(body["workers"]) == 1
    lane = body["workers"][0]
    assert lane["kind"] == "Builder"
    assert lane["slug"] == "lemma_a"
    assert lane["statement"] == "a = a"
    assert lane["file"] is not None
    assert "rfl" in lane["file"]["tail"]
    assert lane["file"]["quiet_sec"] >= 0
    assert body["burn_run"] is not None
    assert body["burn_5h"] is not None


def test_run_idle_keeps_telling_the_last_story(
        workspace: Path, monkeypatch) -> None:
    conn = _open_db(workspace)
    _add_problem(conn, "p")
    db.insert_goal(conn, problem="p", slug="done",
                   lean_path="Problems/p/proofs/done.lean",
                   statement="True", origin="root", status="proved")
    conn.commit()
    conn.close()
    _fake_daemon(monkeypatch, running=False,
                 last_exit={"at": db.now(), "rc": 0, "error": None,
                            "scope": "p"})
    body = _client(workspace).get("/api/run").json()
    assert body["problem"] == "p"
    assert body["goals"]["proved"] == 1
    assert body["workers"] == []
    assert body["burn_run"] is None
