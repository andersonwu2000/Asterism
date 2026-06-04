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
from Tooling.pipeline import _parse_entry_kind, _strip_entry_kind


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
# 1b. Directive stripper — framework removes the line once consumed
# ---------------------------------------------------------------------
# The directive is read exactly once (at sub-goal commit, into
# `goals.entry_kind`); the DB column is the routing SoT thereafter.
# Backward strips the comment from the permanent `proofs/L_<slug>.lean`
# at consume-time so it doesn't linger / propagate into the curated
# Library on migrate. These guard: (a) the line is fully removed with no
# blank residue, (b) sibling rationale `--` comments survive, (c)
# strip-then-parse is idempotent (parse defaults to Builder afterward).

def test_strip_entry_kind_removes_line_no_residue() -> None:
    text = (
        "namespace Problems.x\n\n"
        "-- entry_kind: Builder\n"
        "theorem foo : True := by sorry\n\n"
        "end Problems.x\n"
    )
    out = _strip_entry_kind(text)
    assert "entry_kind" not in out
    # No blank line left where the directive was.
    assert out == (
        "namespace Problems.x\n\n"
        "theorem foo : True := by sorry\n\n"
        "end Problems.x\n"
    )


def test_strip_entry_kind_keeps_rationale_comments() -> None:
    """The directive sits on its own line; adjacent `--` rationale
    comments (the agent's notes) must survive the strip."""
    text = (
        "namespace Problems.x\n\n"
        "-- entry_kind: Builder\n"
        "-- conj_matrix: conjugation lemma, uses `change` to exploit defeq\n"
        "-- second rationale line\n"
        "theorem foo : True := by sorry\n"
    )
    out = _strip_entry_kind(text)
    assert "entry_kind" not in out
    assert "-- conj_matrix: conjugation lemma" in out
    assert "-- second rationale line" in out


def test_strip_entry_kind_noop_when_absent() -> None:
    text = "namespace Problems.x\ntheorem foo : True := by sorry\n"
    assert _strip_entry_kind(text) == text


def test_strip_then_parse_defaults_to_builder() -> None:
    """After the framework consumes + strips, a re-parse of the cleaned
    file sees no directive and defaults to Builder — proving the comment
    is genuinely gone (not just whitespace-mangled into a stale match)."""
    text = (
        "-- entry_kind: Backward\n"
        "theorem t : True := by sorry\n"
    )
    cleaned = _strip_entry_kind(text)
    assert _parse_entry_kind(cleaned) == "Builder"


def test_strip_entry_kind_tolerates_whitespace_variant() -> None:
    """Same loose spacing the parser tolerates must also be stripped, so
    a parsed directive can never survive as residue."""
    text = "  --  entry_kind  :  Backward  \ntheorem t : True := trivial\n"
    out = _strip_entry_kind(text)
    assert "entry_kind" not in out
    assert out == "theorem t : True := trivial\n"


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
