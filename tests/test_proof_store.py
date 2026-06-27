"""Tests for the proof-store chokepoint (`state.proof_store`): atomic write,
ownership/clobber guard, and the DB↔file drift inventory."""
from __future__ import annotations

import sqlite3

import pytest

from Tooling.state import db, proof_store as ps


def _problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES (?, ?, ?, 1)", (name, "m", "t"))
    conn.commit()


def _goal(conn, slug, *, status="open", problem="p"):
    return db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="True", origin="backward", status=status)


# ---------------------------------------------------------------------
# ownership guard
# ---------------------------------------------------------------------

def test_path_owner_and_assert_writable(conn) -> None:
    _problem(conn)
    gid = _goal(conn, "foo")
    rel = "Problems/p/proofs/L_foo.lean"
    assert ps.path_owner(conn, rel) == gid
    assert ps.path_owner(conn, "Problems/p/proofs/L_absent.lean") is None
    # owner may write its own path; a different goal may not
    ps.assert_writable(conn, rel, owner_goal_id=gid)            # no raise
    with pytest.raises(ps.ClobberError):
        ps.assert_writable(conn, rel, owner_goal_id=gid + 999)
    # backslash form normalises to the stored posix path
    assert ps.path_owner(conn, "Problems\\p\\proofs\\L_foo.lean") == gid


# ---------------------------------------------------------------------
# atomic write primitive
# ---------------------------------------------------------------------

def test_atomic_write_creates_and_overwrites(tmp_path) -> None:
    p = tmp_path / "proofs" / "L_a.lean"
    ps.atomic_write(p, "v1")
    assert p.read_text(encoding="utf-8") == "v1"
    ps.atomic_write(p, "v2")                      # overwrite an existing file
    assert p.read_text(encoding="utf-8") == "v2"


def test_atomic_write_leaves_no_backup_or_tmp_straggler(tmp_path) -> None:
    """Regression: overwriting via `atomic_write` must not orphan a `.psbak`
    backup or `.pstmp` scratch file. An earlier verify-window API copied the
    prior content to `<file>.psbak<pid>` and relied on a caller-driven
    `commit_backup`/`rollback` to reap it — no caller ever did, so the backups
    leaked (`Root.lean.psbak<pid>` accumulated under every problem dir). The
    torn-write guarantee is the atomic `os.replace` alone; no copy survives."""
    p = tmp_path / "proofs" / "L_b.lean"
    ps.atomic_write(p, "orig")
    ps.atomic_write(p, "new")
    assert p.read_text(encoding="utf-8") == "new"
    strays = [q.name for q in p.parent.iterdir()
              if ".psbak" in q.name or ".pstmp" in q.name]
    assert strays == [], f"atomic_write left straggler files: {strays}"


# ---------------------------------------------------------------------
# place / remove with ownership
# ---------------------------------------------------------------------

def test_place_proof_refuses_clobber(conn, tmp_path) -> None:
    _problem(conn)
    a = _goal(conn, "owned")
    rel = "Problems/p/proofs/L_owned.lean"
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text("A's committed proof", encoding="utf-8")
    # a DIFFERENT goal placing at A's path is refused before touching disk
    with pytest.raises(ps.ClobberError):
        ps.place_proof(conn, tmp_path, goal_id=a + 999, rel_path=rel,
                       content="B would clobber")
    assert (tmp_path / rel).read_text(encoding="utf-8") == "A's committed proof"
    # the owner may write
    ps.place_proof(conn, tmp_path, goal_id=a, rel_path=rel, content="A v2")
    assert (tmp_path / rel).read_text(encoding="utf-8") == "A v2"


def test_remove_proof_guard(conn, tmp_path) -> None:
    _problem(conn)
    a = _goal(conn, "rm")
    rel = "Problems/p/proofs/L_rm.lean"
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text("x", encoding="utf-8")
    with pytest.raises(ps.ClobberError):
        ps.remove_proof(conn, tmp_path, rel_path=rel, owner_goal_id=a + 999)
    assert (tmp_path / rel).exists()
    ps.remove_proof(conn, tmp_path, rel_path=rel, owner_goal_id=a)
    assert not (tmp_path / rel).exists()


# ---------------------------------------------------------------------
# drift inventory
# ---------------------------------------------------------------------

def test_inventory_clean(conn, tmp_path) -> None:
    _problem(conn)
    _goal(conn, "ok", status="proved")
    rel = "Problems/p/proofs/L_ok.lean"
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text("theorem t : True := trivial\n", encoding="utf-8")
    rep = ps.inventory(conn, tmp_path)
    assert rep.ok(), rep.summary()


def test_inventory_orphan_file(conn, tmp_path) -> None:
    _problem(conn)
    # file present under proofs/, no DB row (placement crashed pre-commit)
    d = tmp_path / "Problems" / "p" / "proofs"
    d.mkdir(parents=True, exist_ok=True)
    (d / "L_orphan.lean").write_text("theorem t : True := by sorry\n",
                                     encoding="utf-8")
    # a real row so the problem is enumerated
    _goal(conn, "real", status="open")
    (d / "L_real.lean").write_text("x", encoding="utf-8")
    rep = ps.inventory(conn, tmp_path)
    assert "Problems/p/proofs/L_orphan.lean" in rep.orphan_files
    assert not rep.missing_files


def test_inventory_missing_file(conn, tmp_path) -> None:
    _problem(conn)
    _goal(conn, "gone", status="proved")          # row says proved, file absent
    rep = ps.inventory(conn, tmp_path)
    assert "Problems/p/proofs/L_gone.lean" in rep.missing_files


def test_inventory_proved_with_sorry(conn, tmp_path) -> None:
    _problem(conn)
    _goal(conn, "fake", status="proved")
    rel = "Problems/p/proofs/L_fake.lean"
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text("theorem t : True := by sorry\n", encoding="utf-8")
    rep = ps.inventory(conn, tmp_path)
    assert "Problems/p/proofs/L_fake.lean" in rep.proved_with_sorry
    assert not rep.ok()
    # a sorry only in a comment is NOT flagged
    (tmp_path / rel).write_text("-- sorry here\ntheorem t : True := trivial\n",
                                encoding="utf-8")
    assert ps.inventory(conn, tmp_path).ok()


def test_inventory_open_row_missing_file_tolerated(conn, tmp_path) -> None:
    # an 'open' goal awaiting placement legitimately has no file yet
    _problem(conn)
    _goal(conn, "pending", status="open")
    assert ps.inventory(conn, tmp_path).ok()
