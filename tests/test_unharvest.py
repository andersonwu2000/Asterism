"""Phase 6 — librarian.un_harvest (rollback decision ①: full-auto
Library take-down when a post-Ingest un-prove revokes the terminal
judgment). Files removed, INDEX section dropped, lifecycle rows +
fail counts cleared; cross-problem dependents surfaced loudly."""
from pathlib import Path

from Tooling.pipeline.librarian import un_harvest
from Tooling.state import db


def _seed(tmp_path, problem="Topology.demo"):
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES (?,'',?)", (problem, db.now()))
    lib = tmp_path / "Library" / "Topology" / "Demo"
    lib.mkdir(parents=True)
    f1 = lib / "Main.lean"
    f1.write_text("theorem demo_main : True := trivial\n", encoding="utf-8")
    conn.execute(
        "INSERT INTO library_decls (problem, slug, lifecycle, target_file,"
        " target_name, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (problem, "demo_main", "cleaned",
         "Library/Topology/Demo/Main.lean",
         "Library.Topology.Demo.demo_main", db.now(), db.now()))
    conn.execute("INSERT INTO librarian_fail_counts (target_id, n,"
                 " updated_at) VALUES (?, 2, ?)", (problem, db.now()))
    conn.execute("INSERT INTO librarian_fail_counts (target_id, n,"
                 " updated_at) VALUES (?, 1, ?)",
                 (f"{problem}\x1fMain.lean", db.now()))
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('Other.problem','',?)", (db.now(),))
    db.mark_library_bridged(conn, problem)
    db.mark_library_bridged(conn, "Other.problem")
    return conn, f1


def test_un_harvest_removes_files_marker_and_rows(tmp_path, capsys):
    problem = "Topology.demo"
    conn, f1 = _seed(tmp_path, problem)
    removed = un_harvest(conn, tmp_path, problem)
    assert removed == 1
    assert not f1.exists()
    # v18: the bridge marker is cleared; the unrelated problem's survives.
    assert db.problem_library_bridged(conn, problem) is False
    assert db.problem_library_bridged(conn, "Other.problem") is True
    assert conn.execute("SELECT count(*) FROM library_decls WHERE"
                        " problem=?", (problem,)).fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM librarian_fail_counts"
                        ).fetchone()[0] == 0


def test_un_harvest_noop_when_never_harvested(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, manifest_path, created_at)"
                 " VALUES ('p','',?)", (db.now(),))
    conn.commit()
    assert un_harvest(conn, tmp_path, "p") == 0


def test_un_harvest_surfaces_cross_problem_dependents(tmp_path, capsys):
    problem = "Topology.demo"
    conn, f1 = _seed(tmp_path, problem)
    other = tmp_path / "Library" / "Other" / "User.lean"
    other.parent.mkdir(parents=True)
    other.write_text("import Library.Topology.Demo.Main\n"
                     "theorem uses_it : True := trivial\n",
                     encoding="utf-8")
    un_harvest(conn, tmp_path, problem)
    out = capsys.readouterr().out
    assert "CRITICAL" in out
    assert "Library.Topology.Demo.Main" in out
    assert other.exists()                      # dependent is NOT deleted
    assert not f1.exists()                     # revoked base still comes down
