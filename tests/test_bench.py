"""Operator bench (owner ruling 2026-08-31).

The fleet ran ten Erdos problems; three (p324/p359/p887) burned 23
rebutted cycles for two bricks. The owner's call: the hopeless ones
stop running — WITHOUT resetting them (their goals, revisions and last
words are assets; shelved is not a terminal state, and neither is
benched). `paused` could not serve: it is derived from awaiting_human,
which means "a question is waiting for the user". `scope` could not
serve either: one SQL LIKE cannot name a keep-list.

Contract: `problems.benched` (additive column) — a benched problem
takes no refill dispatch and no Strategist seat; `asterism bench`
flushes its unleased queue rows so nothing already enqueued fires;
`asterism unbench` puts it back on the live path. State is untouched.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db, groups


def _conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    return c


def _problem(conn, name):
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                 " VALUES (?, ?, 1)", (name, db.now()))
    return name


def test_bench_cli_sets_clears_and_flushes(tmp_path, monkeypatch):
    from Tooling.core.cli.maint import cmd_bench, cmd_unbench
    monkeypatch.chdir(tmp_path)
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.bench")
    q = _problem(conn, "Test.keep")
    db.enqueue(conn, kind="Formalizer", target_id="1", problem=p)
    db.enqueue(conn, kind="Strategist", target_id="9", problem=p,
               target_kind="Group")
    db.enqueue(conn, kind="Formalizer", target_id="2", problem=q)
    conn.commit()
    conn.close()

    assert cmd_bench(argparse.Namespace(problem=p)) == 0
    c2 = db.connect(tmp_path / "asterism.db")
    assert c2.execute("SELECT benched FROM problems WHERE name=?",
                      (p,)).fetchone()[0] == 1
    rows = [tuple(r) for r in c2.execute(
        "SELECT problem, kind FROM queue ORDER BY id")]
    assert rows == [("Test.keep", "Formalizer")], \
        "benching flushes the benched problem's unleased rows only"
    c2.close()

    assert cmd_unbench(argparse.Namespace(problem=p)) == 0
    c3 = db.connect(tmp_path / "asterism.db")
    assert c3.execute("SELECT benched FROM problems WHERE name=?",
                      (p,)).fetchone()[0] == 0
    c3.close()


def test_refill_skips_benched_problems(tmp_path):
    from Tooling.core.dispatcher import refill
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.rb")
    q = _problem(conn, "Test.rk")
    for prob, slug in ((p, "main_b"), (q, "main_k")):
        db.insert_goal(conn, problem=prob, slug=slug,
                       lean_path=f"Problems/{prob}/proofs/L_{slug}.lean",
                       statement="True", origin="root", depth=0)
    conn.execute("UPDATE problems SET benched = 1 WHERE name = ?", (p,))
    conn.commit()
    refill.bfs_refill(conn, running=set())
    rows = [r["problem"] for r in conn.execute("SELECT problem FROM queue")]
    assert rows == [q], "only the unbenched problem's goal is enqueued"


def test_no_strategist_seat_for_a_benched_problem(tmp_path):
    from Tooling.core.dispatcher.triggers import _enqueue_strategist
    conn = _conn(tmp_path)
    p = _problem(conn, "Test.sb")
    top = groups.ensure_top_group(conn, p)
    conn.execute("UPDATE problems SET benched = 1 WHERE name = ?", (p,))
    conn.commit()
    _enqueue_strategist(conn, top, p, priority=10)
    assert conn.execute("SELECT count(*) FROM queue").fetchone()[0] == 0
