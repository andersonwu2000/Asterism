"""entry_kind directive routing.

Backward agent annotates each new sub-goal file with `-- entry_kind:
Builder` or `-- entry_kind: Backward`. Framework parses + persists the
directive on `goals.entry_kind`. Dispatcher's `next_worker_kind` honors
the directive while attempts < BUILDER_THRESHOLD; once attempts reach
the threshold, escalation to Backward is forced regardless (safety net
for an entry_kind=Builder directive that turns out wrong).

Root goal's entry_kind comes directly from `Manifest.entry_kind`
(`## Entry kind` section, parsed at cli init time).
"""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.state import db
from Tooling.pipeline import _parse_entry_kind


# ---------------------------------------------------------------------
# 1. Directive parser
# ---------------------------------------------------------------------

def test_parse_entry_kind_builder() -> None:
    text = (
        "namespace Problems.x\n\n"
        "-- entry_kind: Builder\n"
        "theorem foo : True := by sorry\n\n"
        "end Problems.x\n"
    )
    assert _parse_entry_kind(text) == "Builder"


def test_parse_entry_kind_backward() -> None:
    text = (
        "namespace Problems.x\n\n"
        "-- entry_kind: Backward\n"
        "theorem foo : True := by sorry\n\n"
        "end Problems.x\n"
    )
    assert _parse_entry_kind(text) == "Backward"


def test_parse_entry_kind_default_when_missing() -> None:
    """A sub-goal file without the directive defaults to Builder so the
    legacy attempts-only routing still applies (no behavior change)."""
    text = (
        "namespace Problems.x\n\n"
        "theorem foo : True := by sorry\n\n"
        "end Problems.x\n"
    )
    assert _parse_entry_kind(text) == "Builder"


def test_parse_entry_kind_tolerates_whitespace() -> None:
    text = "  --  entry_kind  :  Backward  \ntheorem t : True := trivial\n"
    assert _parse_entry_kind(text) == "Backward"


def test_parse_entry_kind_unrecognized_value_falls_back_to_builder() -> None:
    """`Strategist` etc. aren't valid kinds yet; treat as missing."""
    text = "-- entry_kind: Strategist\ntheorem t : True := trivial\n"
    assert _parse_entry_kind(text) == "Builder"


# ---------------------------------------------------------------------
# 2. DB roundtrip — insert_goal writes entry_kind, get_goal reads it
# ---------------------------------------------------------------------

def test_insert_goal_persists_entry_kind(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    gid_b = db.insert_goal(
        conn, problem="p", slug="b", lean_path="Problems/p/B.lean",
        statement="T", origin="root", entry_kind="Builder",
    )
    gid_back = db.insert_goal(
        conn, problem="p", slug="back", lean_path="Problems/p/Back.lean",
        statement="T", origin="backward", entry_kind="Backward",
    )
    assert db.get_goal(conn, gid_b)["entry_kind"] == "Builder"
    assert db.get_goal(conn, gid_back)["entry_kind"] == "Backward"


def test_insert_goal_default_is_builder(conn: sqlite3.Connection) -> None:
    """Defaulting matters for the migration path — existing rows on
    disk DBs get 'Builder' via the column DEFAULT."""
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) "
        "VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    gid = db.insert_goal(
        conn, problem="p", slug="g", lean_path="Problems/p/G.lean",
        statement="T", origin="root",
    )
    assert db.get_goal(conn, gid)["entry_kind"] == "Builder"
