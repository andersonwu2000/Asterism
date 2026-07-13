"""Proved-brick catalog companion (2026-07-13, user call): exact
statements move out of inline context into a machine-generated
`CATALOG.md`; inline surfaces carry slugs (Forward/Strategist index)
or a two-line pointer (Backward/Builder, which already have the
per-goal pre-search surface). Replaces the Strategist's hand-copied
directive catalog as the citation SoT — generated from goal records,
so pipeline renames can never make it drift."""
import sqlite3

import pytest

from Tooling.agent import context as ctx
from Tooling.agent import phase2_context
from Tooling.state import db


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?,?,?)",
        ("P", "P/Manifest.md", db.now()),
    )
    c.commit()
    return c


def _goal(conn, slug, status="proved", kind="theorem"):
    conn.execute(
        "INSERT INTO goals (problem, slug, lean_path, statement, kind,"
        " origin, status, depth, created_at, updated_at) VALUES "
        "('P', ?, ?, ?, ?, 'forward', ?, 0, ?, ?)",
        (slug, f"P/proofs/L_{slug}.lean",
         f"theorem {slug} : 1 + 1 = 2", kind, status, db.now(), db.now()))
    conn.commit()


def test_companion_carries_full_statements(conn, tmp_path):
    _goal(conn, "brick_a")
    _goal(conn, "brick_b", kind="def")
    _goal(conn, "still_open", status="open")
    rows = ctx.write_catalog_companion(conn, "P", tmp_path)
    assert [r["slug"] for r in rows] == ["brick_a", "brick_b"]
    body = (tmp_path / ctx.CATALOG_COMPANION).read_text(encoding="utf-8")
    assert "## brick_a  (theorem)" in body
    assert "theorem brick_a : 1 + 1 = 2" in body
    assert "L_brick_a.lean" in body
    assert "still_open" not in body


def test_companion_empty_kb_writes_nothing(conn, tmp_path):
    assert ctx.write_catalog_companion(conn, "P", tmp_path) == []
    assert not (tmp_path / ctx.CATALOG_COMPANION).exists()


def test_worker_pointer_is_two_lines_not_a_list(conn, tmp_path):
    for i in range(30):
        _goal(conn, f"brick_{i}")
    lines = ctx._section_catalog_pointer(conn, "P", tmp_path)
    text = "\n".join(lines)
    assert "30 proved bricks" in text and ctx.CATALOG_COMPANION in text
    # pointer, not an index: no per-brick lines
    assert "brick_7" not in text
    assert (tmp_path / ctx.CATALOG_COMPANION).exists()


def test_forward_inventory_is_slug_index_with_companion(conn, tmp_path):
    _goal(conn, "brick_a")
    _goal(conn, "brick_b")
    lines = phase2_context._section_library_inventory(conn, "P", tmp_path)
    text = "\n".join(lines)
    # prompt-pinned header kept verbatim (forward.md points at it)
    assert text.startswith("## Library (proved lemmas in this problem)")
    assert "- `brick_a`" in text and "- `brick_b`" in text
    # statements no longer inline — they live in the companion
    assert "1 + 1 = 2" not in text
    assert "1 + 1 = 2" in (tmp_path / ctx.CATALOG_COMPANION).read_text(
        encoding="utf-8")


def test_strategist_index_present_and_wired(conn, tmp_path):
    _goal(conn, "brick_a")
    lines = phase2_context._section_catalog_index_strategist(
        conn, "P", tmp_path)
    text = "\n".join(lines)
    assert "## Proved catalog (index)" in text and "- `brick_a`" in text
    assert "1 + 1 = 2" not in text
    # wiring pins: all three compile paths carry the catalog surface
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    p2 = (root / "Tooling" / "agent" / "phase2_context.py").read_text(
        encoding="utf-8")
    assert "_section_catalog_index_strategist(conn, problem, attempts_dir)" in p2
    assert "_section_library_inventory(conn, problem, attempts_dir)" in p2
    c = (root / "Tooling" / "agent" / "context.py").read_text(
        encoding="utf-8")
    assert "_section_catalog_pointer(conn, str(goal[\"problem\"]), attempts_dir)" in c
