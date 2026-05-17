"""Phase 2 — compile_context Strategist directive + brief sections.

Covers Step 5 acceptance: `compile_context` accepts `decision_id`
parameter, renders `## Strategist directive` when problems.
strategist_directive is non-empty, renders `## Strategist brief` when
decision_id points to a Strategist Inject decision row.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.agent.context import compile_context
from Tooling.state import db, manifest as manifest_mod


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a tmp workspace with Problems/p/{Manifest.md,proofs/}."""
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    (pdir / "proofs").mkdir()
    (pdir / "Root.lean").write_text(
        "theorem main : T := by sorry\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_root(conn: sqlite3.Connection) -> int:
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean", statement="T",
        origin="root", depth=0, entry_kind="Backward",
    )


def _make_attempts_dir(workspace: Path) -> Path:
    """Set up `.attempts/<pid>/` to satisfy compile_context's path
    walking (.attempts/<pid> -> .attempts -> workspace)."""
    pid = "test-pid"
    attempts_dir = workspace / ".attempts" / pid
    attempts_dir.mkdir(parents=True)
    return attempts_dir


def _read_context(attempts_dir: Path) -> str:
    return (attempts_dir / "Context.md").read_text(encoding="utf-8")


def _fake_manifest() -> manifest_mod.Manifest:
    return manifest_mod.Manifest(problem="p", statement="T")


# ---------------------------------------------------------------------
# Directive section
# ---------------------------------------------------------------------

def test_no_directive_no_section(workspace: Path,
                                 conn: sqlite3.Connection) -> None:
    """Default (no directive set) → no `## Strategist directive` section."""
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" not in text


def test_directive_rendered_when_set(workspace: Path,
                                     conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = 'p'",
        ("Library now has contour_deformation_piecewise; prefer it.",),
    )
    conn.commit()

    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" in text
    assert "contour_deformation_piecewise" in text


def test_empty_directive_not_rendered(workspace: Path,
                                      conn: sqlite3.Connection) -> None:
    """Whitespace-only directive treated as absent."""
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = 'p'",
        ("   \n   ",),
    )
    conn.commit()

    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" not in text


# ---------------------------------------------------------------------
# Brief section
# ---------------------------------------------------------------------

def _insert_decision(conn: sqlite3.Connection, *, kind: str,
                     brief: str | None = None,
                     reason: str | None = None) -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, reason, payload,"
        " created_at, updated_at)"
        " VALUES ('p', 1, 'routine', ?, ?, ?, '{}', ?, ?)",
        (kind, brief, reason, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_no_decision_id_no_brief_section(workspace: Path,
                                         conn: sqlite3.Connection) -> None:
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=None,
    )
    text = _read_context(attempts_dir)
    assert "## Strategist brief" not in text


def test_brief_rendered_when_decision_id_set(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    did = _insert_decision(
        conn, kind="Inject",
        brief="## Need\nLemma X for contour deformation",
    )
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=did,
    )
    text = _read_context(attempts_dir)
    assert "## Strategist brief" in text
    assert "contour deformation" in text


def test_brief_skipped_when_brief_column_null(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve decision (no brief, only reason) → brief section
    not rendered."""
    did = _insert_decision(conn, kind="ConfirmShelve",
                           reason="truly dead")
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=did,
    )
    text = _read_context(attempts_dir)
    assert "## Strategist brief" not in text


def test_both_directive_and_brief_render(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Directive + Inject brief both present → both sections appear,
    directive first (problem-level standing)."""
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = 'p'",
        ("Prefer L_alpha over manual case-split.",),
    )
    conn.commit()
    did = _insert_decision(
        conn, kind="Inject",
        brief="## Need\nFollow up on L_alpha",
    )
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=did,
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" in text
    assert "## Strategist brief" in text
    # Ordering: directive before brief
    assert text.index("## Strategist directive") < text.index("## Strategist brief")


def test_brief_decision_id_nonexistent(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """decision_id pointing to no-such-row → no brief, no crash."""
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, mfst=_fake_manifest(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=99999,
    )
    text = _read_context(attempts_dir)
    assert "## Strategist brief" not in text
