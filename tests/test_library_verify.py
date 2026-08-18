"""`asterism library-verify` — whole-Library coherence gate (P1).

Covers the printer-free `_library_consistency_findings` (v18: DB <-> disk
over the placed decl set + bridge-marker agreement; the INDEX.md three-way
checks are structurally impossible and retired). The placed set is
`library_decls.lifecycle IN ('migrated','cleaned')`; 'cited'/'dropped' decls
are not placed and must never participate (the regression that motivated the
gate: a dedup-dropped decl left exposed after harvest — now impossible by
construction, exposure derives from the DB).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.core import cli
from Tooling.state import db


# ---------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------

def _conn(tmp: Path):
    conn = db.connect(tmp / "t.db")
    db.init_schema(conn)
    # Unit test inserts library_decls without a backing problems row; the
    # FK to problems(name) is irrelevant to the consistency logic.
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


def _add(conn, *, problem, slug, name, file, lifecycle):
    conn.execute(
        "INSERT INTO library_decls (problem, slug, target_name, target_file, "
        "lifecycle, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (problem, slug, name, file, lifecycle, "t", "t"))
    conn.commit()


def _disk(tmp: Path, *rels: str):
    for rel in rels:
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("-- lib file\n", encoding="utf-8")


def _bridge(conn, *problems: str):
    """Mark problems bridged (v18 done-marker; problems row seeded on
    demand — FK is OFF in these fixtures but the marker UPDATE needs the
    row to exist)."""
    for prob in problems:
        if conn.execute("SELECT 1 FROM problems WHERE name=?",
                        (prob,)).fetchone() is None:
            conn.execute(
                "INSERT INTO problems (name, created_at,"
                " bootstrap_done) VALUES (?, 't', 1)", (prob,))
        db.mark_library_bridged(conn, prob)


def _statuses(findings):
    return [s for s, _ in findings]


def _fails(findings):
    return [m for s, m in findings if s == "FAIL"]


def _warns(findings):
    return [m for s, m in findings if s == "WARN"]


# ---------------------------------------------------------------------
# consistency — clean
# ---------------------------------------------------------------------

def test_clean_library_all_ok(tmp_path):
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _add(conn, problem="P", slug="bar", name="Library.P.bar",
         file="Library/P/B.lean", lifecycle="migrated")
    _disk(tmp_path, "Library/P/A.lean", "Library/P/B.lean")
    _bridge(conn, "P")
    findings = cli._library_consistency_findings(conn, tmp_path)
    assert "FAIL" not in _statuses(findings)
    assert "WARN" not in _statuses(findings)


def test_cited_and_dropped_decls_do_not_participate(tmp_path):
    # 'cited'/'dropped' decls have no file contribution — a dropped decl still
    # listed in INDEX is the eckart_young regression; here it is NOT placed, so
    # an INDEX that omits it is correct and clean.
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _add(conn, problem="P", slug="dup", name="Library.P.dup",
         file="Library/P/A.lean", lifecycle="dropped")
    _add(conn, problem="P", slug="ext", name="Library.P.ext",
         file="Library/P/A.lean", lifecycle="cited")
    _disk(tmp_path, "Library/P/A.lean")
    _bridge(conn, "P")
    findings = cli._library_consistency_findings(conn, tmp_path)
    assert "FAIL" not in _statuses(findings)


# ---------------------------------------------------------------------
# I5 — a CLEANED file keeping the `import Mathlib` umbrella WARNs (decide
# import-min mechanically minimises it; a survivor is the rare fallback)
# ---------------------------------------------------------------------

def test_cleaned_file_with_umbrella_import_warns(tmp_path):
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _add(conn, problem="P", slug="bar", name="Library.P.bar",
         file="Library/P/B.lean", lifecycle="cleaned")
    (tmp_path / "Library/P").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Library/P/A.lean").write_text(            # umbrella survivor
        "import Mathlib\ntheorem foo : True := trivial\n", encoding="utf-8")
    (tmp_path / "Library/P/B.lean").write_text(            # precise imports
        "import Mathlib.Logic.Basic\ntheorem bar : True := trivial\n",
        encoding="utf-8")
    _bridge(conn, "P")
    findings = cli._library_consistency_findings(conn, tmp_path)
    assert "FAIL" not in _statuses(findings)              # builds → never a FAIL
    warns = _warns(findings)
    assert any("import Mathlib" in w and "A.lean" in w for w in warns)
    assert not any("B.lean" in w for w in warns)          # precise → no warn


def test_migrated_file_with_umbrella_not_warned(tmp_path):
    # 'migrated'-but-not-'cleaned' files legitimately still carry the umbrella.
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="migrated")
    (tmp_path / "Library/P").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Library/P/A.lean").write_text(
        "import Mathlib\ntheorem foo : True := trivial\n", encoding="utf-8")
    _bridge(conn, "P")
    warns = _warns(cli._library_consistency_findings(conn, tmp_path))
    assert not any("import Mathlib" in w for w in warns)


# ---------------------------------------------------------------------
# consistency — each drift class FAILs
# ---------------------------------------------------------------------

def test_orphan_disk_file_fails(tmp_path):
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _disk(tmp_path, "Library/P/A.lean", "Library/P/Orphan.lean")  # extra file
    _bridge(conn, "P")
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any("orphan" in m and "Orphan.lean" in m for m in fails)


def test_db_row_pointing_at_missing_file_fails(tmp_path):
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/Gone.lean", lifecycle="cleaned")
    _disk(tmp_path, "Library/P/A.lean")        # Gone.lean never written
    _bridge(conn, "P")
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any("missing file" in m and "Gone.lean" in m for m in fails)


def test_stale_bridge_marker_fails(tmp_path):
    # v18 successor of the "fully stale INDEX section" class: a problem
    # marked bridged with ZERO placed decls (un-harvested / rows deleted
    # behind the marker) is stale provenance -> FAIL.
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _disk(tmp_path, "Library/P/A.lean")
    _bridge(conn, "P", "Q")                    # Q bridged, nothing placed
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any(m.startswith("Q:") and "stale marker" in m for m in fails)
    # P (bridged + placed) reports OK, not FAIL
    assert not any(m.startswith("P:") for m in fails)


def test_db_placed_but_not_bridged_warns_not_fails(tmp_path):
    # migrated decls, marker not yet set = not yet bridged (legit
    # mid-flight) -> WARN only.
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="migrated")
    _disk(tmp_path, "Library/P/A.lean")
    findings = cli._library_consistency_findings(conn, tmp_path)
    assert "FAIL" not in _statuses(findings)
    assert any("not bridged yet" in m for m in _warns(findings))
