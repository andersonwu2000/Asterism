"""`ASTERISM_BLOCKED_KINDS` — an operator hold on dispatch kinds
(2026-08-30, experiment knob). The quota ledger already blocks kinds
whose seat is out of quota; the operator needs the same lever by hand:
run a daemon on a live problem and let ONLY the Strategist move (e.g.
to observe a routine audit on an old tree without spending a formalizer
quota on its 800 open fragments).
"""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.core.dispatcher import refill
from Tooling.state import db


@pytest.mark.parametrize("raw,want", [
    ("Formalizer", {"Formalizer"}),
    (" formalizer , LIBRARIAN ", {"Formalizer", "Librarian"}),
    ("", set()),
    (None, set()),
    ("bogus", set()),
])
def test_env_blocked_kinds_parses_and_normalizes(monkeypatch, raw, want):
    if raw is None:
        monkeypatch.delenv("ASTERISM_BLOCKED_KINDS", raising=False)
    else:
        monkeypatch.setenv("ASTERISM_BLOCKED_KINDS", raw)
    assert refill.env_blocked_kinds() == want


def test_bfs_refill_honours_the_env_hold(conn: sqlite3.Connection, monkeypatch):
    conn.execute("INSERT INTO problems (name, created_at, bootstrap_done) "
                 "VALUES (?, ?, 1)", ("p", db.now()))
    gid = db.insert_goal(conn, problem="p", slug="main",
                         lean_path="Problems/p/proofs/L_main.lean",
                         statement="True", origin="root", depth=0)
    conn.commit()
    monkeypatch.setenv("ASTERISM_BLOCKED_KINDS", "Formalizer")
    refill.bfs_refill(conn, running=set(),
                      blocked_kinds=refill.env_blocked_kinds())
    assert db.queue_size(conn) == 0, "the held kind is not enqueued"
    monkeypatch.delenv("ASTERISM_BLOCKED_KINDS")
    refill.bfs_refill(conn, running=set(), blocked_kinds=refill.env_blocked_kinds())
    assert db.queue_size(conn) == 1


def test_blocked_kinds_reads_the_yaml_key_with_env_precedence(
        tmp_path, monkeypatch):
    """The hold is a per-run knob the console must be able to set (HID
    §1.4), so `dispatch.blocked_kinds` is the canonical home and the env
    var stays the override — the same shape every other dispatch knob
    resolves through."""
    from Tooling.core import config as _cfg
    _cfg._reset_cache()
    monkeypatch.delenv("ASTERISM_BLOCKED_KINDS", raising=False)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  blocked_kinds: Formalizer,Librarian\n",
        encoding="utf-8")
    try:
        assert refill.env_blocked_kinds(tmp_path) == {"Formalizer",
                                                      "Librarian"}
        monkeypatch.setenv("ASTERISM_BLOCKED_KINDS", "Strategist")
        assert refill.env_blocked_kinds(tmp_path) == {"Strategist"}
    finally:
        _cfg._reset_cache()
