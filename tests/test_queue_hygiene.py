"""Queue/status hygiene (owner order 2026-08-31: 「現在就處理掉」).

Field, same night: `in_flight_leases` (leased queue rows) was read as
"agents in flight" — the stop-window status said 34 while 9 pipelines
ran, and serve displayed the number as "34 agent(s)". Separately, a
fired routine verdict whose group was CLOSED after the audit re-seated
a Strategist every tick forever: T1.6 enqueued, the pop loop's
settled-target skip deleted the row, T1.6 enqueued again — 5,393
`[dispatch] skip` lines in three hours on group 717.

Contract now: `in_flight` counts RUNNING PIPELINES (the number a human
means by "agents"); `in_flight_leases` keeps counting leased queue rows
(diagnostic); serve's consent/preview surfaces read `in_flight`. A
Strategist seat can only be enqueued for an ACTIVE group, and a fired
verdict whose group is no longer active is stamped acted (moot) instead
of re-seating forever.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from Tooling.state import db, groups


def _conn(tmp_path: Path):
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    return c


def _problem(conn, name):
    conn.execute("INSERT INTO problems (name, created_at)"
                 " VALUES (?, '2026-08-31T00:00:00Z')", (name,))
    return name


def _seats(conn):
    return {(r["target_id"], r["target_kind"]) for r in conn.execute(
        "SELECT target_id, target_kind FROM queue WHERE kind = 'Strategist'")}


# ─── the enqueue chokepoint refuses non-active groups ────────────────

def test_enqueue_strategist_refuses_a_non_active_group(tmp_path):
    from Tooling.core.dispatcher.triggers import _enqueue_strategist
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.qh")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="closed later")
    conn.execute("UPDATE groups SET status = 'closed' WHERE id = ?", (sub,))
    conn.commit()
    _enqueue_strategist(conn, sub, p, priority=10)
    assert (str(sub), "Group") not in _seats(conn)


# ─── a fired verdict on a dead group extinguishes, not re-seats ──────

def test_fired_verdict_on_a_closed_group_extinguishes(tmp_path):
    from Tooling.core.dispatcher import strategist_triggers
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.qh2")
    top = groups.ensure_top_group(conn, p)
    sub = groups.open_group(conn, problem=p, parent_group_id=top,
                            charter="audited then closed")
    conn.execute(
        "INSERT INTO routine_verdicts (problem, group_id, pipeline_id,"
        " verdict_json, fired_json, unaudited_json, fired, created_at)"
        " VALUES (?, ?, 'pid-1', '{}', '[]', '[]', 1, ?)",
        (p, sub, db.now()))
    conn.execute("UPDATE groups SET status = 'closed' WHERE id = ?", (sub,))
    conn.commit()
    strategist_triggers(conn, running=set(), interval_min=60.0)
    assert (str(sub), "Group") not in _seats(conn)
    acted = conn.execute(
        "SELECT acted_at FROM routine_verdicts WHERE group_id = ?",
        (sub,)).fetchone()[0]
    assert acted is not None, "a moot verdict must extinguish itself"


# ─── status: in_flight = running pipelines, not leased queue rows ────

def test_daemon_status_reports_running_pipelines_not_leases(tmp_path):
    from Tooling.core.cli import daemon_status
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.qh3")
    db.record_pipeline_start(conn, pipeline_id="qh-a", kind="Strategist",
                             target_id="1", target_kind="Group")
    db.record_pipeline_start(conn, pipeline_id="qh-b", kind="Formalizer",
                             target_id="2", target_kind="Goal")
    db.record_pipeline_start(conn, pipeline_id="qh-c", kind="Formalizer",
                             target_id="3", target_kind="Goal")
    db.finish_pipeline(conn, pipeline_id="qh-c", status="succeeded",
                       outcome="done")
    for i in range(3):
        db.enqueue(conn, kind="Formalizer", target_id=str(100 + i), problem=p)
        db.pop_queue(conn, lease_owner=os.getpid())
    conn.commit()
    st = daemon_status(tmp_path)
    assert st["in_flight"] == 2, "two pipelines still running"
    assert st["in_flight_leases"] == 3, "three leased queue rows"


# ─── serve counts agents from in_flight ──────────────────────────────

def test_serve_counts_agents_from_in_flight(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from Tooling.serve.app import create_app
    import Tooling.core.cli as _cli
    monkeypatch.setattr(_cli, "daemon_status", lambda ws: {
        "running": True, "pid": 111, "scope": "Cmp.a",
        "in_flight": 2, "in_flight_leases": 34, "gateway": "ready"})
    c = TestClient(create_app(tmp_path))
    d = c.get("/api/shutdown/preview").json()
    assert d["daemon"]["in_flight"] == 2, "agents = running pipelines"
    r = c.post("/api/shutdown", json={})
    assert r.status_code == 409
    assert "2 agent" in r.json()["detail"]
    assert "34" not in r.json()["detail"]
