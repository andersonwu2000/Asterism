"""entry_kind retirement invariants (v33, Formalizer merge).

The routing column and its `-- entry_kind:` directive parse are GONE —
the merged worker decides prove-vs-split itself. What survives is the
STRIP (Library hygiene: a legacy-shaped stub's directive comment must
not linger in proofs/ or propagate into the curated Library), plus the
schema invariant that the column stays dead.
"""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.pipeline import _strip_entry_kind
from Tooling.state import db


# ---------------------------------------------------------------------
# Legacy-directive strip (the surviving half)
# ---------------------------------------------------------------------

def test_strip_entry_kind_removes_line_no_residue() -> None:
    text = (
        "namespace Problems.p\n"
        "\n"
        "-- entry_kind: Builder\n"
        "theorem foo : True := by sorry\n"
        "\n"
        "end Problems.p\n"
    )
    out = _strip_entry_kind(text)
    assert "entry_kind" not in out
    assert "\ntheorem foo" in out


def test_strip_entry_kind_keeps_rationale_comments() -> None:
    text = (
        "-- entry_kind: Backward\n"
        "-- rationale: this lemma bridges the telescoping step\n"
        "theorem foo : True := by sorry\n"
    )
    out = _strip_entry_kind(text)
    assert "entry_kind" not in out
    assert "rationale: this lemma bridges" in out


def test_strip_entry_kind_noop_when_absent() -> None:
    text = "theorem foo : True := by sorry\n"
    assert _strip_entry_kind(text) == text


def test_strip_entry_kind_tolerates_whitespace_variant() -> None:
    text = ("  --   entry_kind :  Builder   trailing words\n"
            "theorem f : True := by sorry\n")
    out = _strip_entry_kind(text)
    assert "entry_kind" not in out


# ---------------------------------------------------------------------
# Schema invariants — the column stays dead
# ---------------------------------------------------------------------

def test_goals_table_has_no_entry_kind_column(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
    assert "entry_kind" not in cols


def test_insert_goal_rejects_entry_kind_kwarg(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at,"
        " bootstrap_done) VALUES ('p', 'Problems/p/Manifest.md', ?, 1)",
        (db.now(),),
    )
    with pytest.raises(TypeError):
        db.insert_goal(
            conn, problem="p", slug="main",
            lean_path="Problems/p/Root.lean", statement="True",
            origin="root", entry_kind="Builder",  # type: ignore[call-arg]
        )


def test_second_init_schema_does_not_resurrect_entry_kind(
    conn: sqlite3.Connection,
) -> None:
    """Review 07-27 #4: the additive migration loop must not re-add the
    column a later versioned migration dropped — every daemon start runs
    apply(), so a bare guard means permanent schema drift."""
    from Tooling.state import db_migrations
    db_migrations.apply(conn)  # second startup
    cols = {r[1] for r in conn.execute("PRAGMA table_info(goals)")}
    assert "entry_kind" not in cols
