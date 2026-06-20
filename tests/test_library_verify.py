"""`asterism library-verify` — whole-Library coherence gate (P1).

Covers the printer-free `_library_consistency_findings` (INDEX <-> disk <-> DB
over the placed decl set) + the INDEX parser. The placed set is
`library_decls.lifecycle IN ('migrated','cleaned')`; 'cited'/'dropped' decls
are not placed and must never participate (the regression that motivated the
gate: a dedup-dropped decl left lingering in INDEX).
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


def _index(tmp: Path, sections: "dict[str, list[tuple[str, str]]]"):
    lines = ["# Library Index", ""]
    for prob, entries in sections.items():
        lines.append(f"## {prob}")
        lines.append("")
        lines.append("_Harvested … — n declaration(s)._")
        lines.append("")
        for name, rel in entries:
            lines.append(f"- `{name}` → `{rel}`")
        lines.append("")
    lib = tmp / "Library"
    lib.mkdir(parents=True, exist_ok=True)
    (lib / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")


def _statuses(findings):
    return [s for s, _ in findings]


def _fails(findings):
    return [m for s, m in findings if s == "FAIL"]


def _warns(findings):
    return [m for s, m in findings if s == "WARN"]


# ---------------------------------------------------------------------
# INDEX parser
# ---------------------------------------------------------------------

def test_parse_index_sections_and_entries(tmp_path):
    _index(tmp_path, {
        "Geometry.x": [("Library.G.X.foo", "Library/G/X.lean"),
                       ("Library.G.X.bar", "Library/G/X.lean")],
        "Algebra.y": [("Library.A.Y.baz", "Library/A/Y.lean")],
    })
    parsed = cli._parse_library_index(tmp_path / "Library" / "INDEX.md")
    assert parsed["Geometry.x"] == {
        ("Library.G.X.foo", "Library/G/X.lean"),
        ("Library.G.X.bar", "Library/G/X.lean")}
    assert parsed["Algebra.y"] == {("Library.A.Y.baz", "Library/A/Y.lean")}


def test_parse_index_absent_is_empty(tmp_path):
    assert cli._parse_library_index(tmp_path / "nope" / "INDEX.md") == {}


def test_parse_index_ignores_non_entry_lines(tmp_path):
    # Preamble / harvest line / gate-B status line carry no 2-backtick entry.
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / "INDEX.md").write_text(
        "# Library Index\n\n## P\n\n_Harvested … — 1 declaration(s)._\n\n"
        "- `Library.P.f` → `Library/P.lean`\n\n"
        "Gate B (root re-derivation): PASSED — original `theorem main`.\n",
        encoding="utf-8")
    parsed = cli._parse_library_index(tmp_path / "INDEX.md")
    # only the real entry, not the gate-B line's backticked `theorem main`
    assert parsed["P"] == {("Library.P.f", "Library/P.lean")}


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
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean"),
                            ("Library.P.bar", "Library/P/B.lean")]})
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
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean")]})
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
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean"),
                            ("Library.P.bar", "Library/P/B.lean")]})
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
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean")]})
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
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean")]})
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any("orphan" in m and "Orphan.lean" in m for m in fails)


def test_db_row_pointing_at_missing_file_fails(tmp_path):
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/Gone.lean", lifecycle="cleaned")
    _disk(tmp_path, "Library/P/A.lean")        # Gone.lean never written
    _index(tmp_path, {})
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any("missing file" in m and "Gone.lean" in m for m in fails)


def test_index_entry_missing_file_fails(tmp_path):
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _disk(tmp_path, "Library/P/A.lean")
    # INDEX claims a second file that is not on disk and has no DB row.
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean"),
                            ("Library.P.ghost", "Library/P/Ghost.lean")]})
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any("INDEX entry points to a missing file" in m
               and "Ghost.lean" in m for m in fails)


def test_stale_index_overclaim_fails(tmp_path):
    # The eckart_young scenario: a decl present in INDEX but only 'dropped' in
    # DB (its file still exists for other decls) -> INDEX/DB set mismatch FAIL.
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _add(conn, problem="P", slug="dup", name="Library.P.dup",
         file="Library/P/A.lean", lifecycle="dropped")
    _disk(tmp_path, "Library/P/A.lean")
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean"),
                            ("Library.P.dup", "Library/P/A.lean")]})
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any("INDEX/DB placed-set mismatch" in m and "INDEX-only" in m
               for m in fails)


def test_db_placed_but_no_index_section_warns_not_fails(tmp_path):
    # migrated decls with no INDEX section = not yet bridged (legit mid-flight).
    conn = _conn(tmp_path)
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="migrated")
    _disk(tmp_path, "Library/P/A.lean")
    _index(tmp_path, {})                       # no section for P
    findings = cli._library_consistency_findings(conn, tmp_path)
    assert "FAIL" not in _statuses(findings)
    assert any("no INDEX section" in m for m in _warns(findings))


def test_index_section_for_unplaced_problem_fails(tmp_path):
    # INDEX has a section but DB has zero placed decls for it -> fully stale.
    conn = _conn(tmp_path)
    _disk(tmp_path, "Library/P/A.lean")
    _add(conn, problem="P", slug="foo", name="Library.P.foo",
         file="Library/P/A.lean", lifecycle="cleaned")
    _index(tmp_path, {"P": [("Library.P.foo", "Library/P/A.lean")],
                      "Q": [("Library.Q.bar", "Library/P/A.lean")]})
    fails = _fails(cli._library_consistency_findings(conn, tmp_path))
    assert any(m.startswith("Q:") and "no placed" in m for m in fails)
