"""`asterism revive` on a `refuted` problem (2026-08-30): the terminal a
kernel-disproved root reaches is left the same way `revoked` is — by
the operator's re-grind decision, back to `active` with the liveness
stamp cleared."""
from __future__ import annotations

import argparse

from Tooling.state import db, transitions


def _problem(conn, state):
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('Test.rv', 't')")
    db.set_problem_ingested(conn, "Test.rv")
    transitions.apply_problem_transition(conn, "Test.rv", state,
                                         event="ingest_refuted" if state == "refuted"
                                         else "ingest_direct")
    conn.commit()


def test_revive_takes_a_refuted_problem_back_to_active(tmp_path, monkeypatch):
    from Tooling.core.cli import maint
    path = tmp_path / "asterism.db"
    orig_connect = db.connect
    conn = orig_connect(path)
    db.init_schema(conn)
    _problem(conn, "refuted")
    conn.close()
    # the command opens (and closes) its own connection to the same file
    monkeypatch.setattr(db, "connect", lambda *a, **k: orig_connect(path))
    rc = maint.cmd_revive(argparse.Namespace(problem="Test.rv"))
    assert rc == 0
    check = orig_connect(path)
    row = check.execute("SELECT state, ingested_at FROM problems").fetchone()
    assert row["state"] == "active" and row["ingested_at"] is None


def test_revive_still_refuses_a_live_problem(tmp_path, monkeypatch):
    from Tooling.core.cli import maint
    conn = db.connect(tmp_path / "asterism.db")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at) VALUES ('Test.rv', 't')")
    conn.commit()
    monkeypatch.setattr(db, "connect", lambda *a, **k: conn)
    assert maint.cmd_revive(argparse.Namespace(problem="Test.rv")) == 1
