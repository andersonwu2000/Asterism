"""Mechanical migrate pre-pass wiring (librarian._mechanical_migrate_file
+ _commit_migrated_file). Offline — verifiers injected, no gateway/LLM.

Verifies the Phase-1 path assembles a classified file by pure relabel and
commits it through the shared gate without ever spawning an agent.
"""
from __future__ import annotations

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib

PNS = "Problems.p"  # problem name "p" → namespace Problems.p


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at, "
              "bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def _seed_classified(conn, slug, stmt, target_file, order):
    g = db.insert_goal(conn, problem="p", slug=slug,
                       lean_path=f"proofs/L_{slug}.lean",
                       statement=stmt, origin="backward", kind="theorem")
    conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
    conn.commit()
    db.upsert_library_decl(conn, problem="p", slug=slug, source_goal_id=g)
    db.set_library_verdict(conn, problem="p", slug=slug, verdict="keep")
    db.set_library_classification(conn, problem="p", slug=slug,
                                  target_file=target_file, target_name=None,
                                  file_order=order)


def _write_proof(workspace, slug, body):
    pdir = workspace / "Problems" / "p" / "proofs"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"L_{slug}.lean").write_text(body, encoding="utf-8")


def test_mechanical_assembles_self_contained_file(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\n"
                 f"import {PNS}.Defs\n"
                 f"namespace {PNS}\n"
                 "theorem lem_a : True := by trivial\n"
                 f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    assert text is not None
    assert "namespace Library.P.Foo" in text
    assert "theorem lem_a : True := by trivial" in text
    assert "Problems." not in text


def test_mechanical_declines_when_no_proof_file(conn, tmp_path):
    # classified decl with no L_<slug>.lean on disk → None (LLM path)
    _seed_classified(conn, "ghost", "True", "Library/P/Bar.lean", 0)
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["lifecycle"] == "classified"]
    text = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file="Library/P/Bar.lean",
        target_module="Library.P.Bar", rows=rows)
    assert text is None


def test_commit_migrated_file_marks_all(conn, tmp_path):
    # End-to-end of the shared commit with injected (passing) verifiers:
    # assemble mechanically, then commit → both decls become 'migrated'.
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _seed_classified(conn, "lem_b", "True", tf, 1)
    for slug in ("lem_a", "lem_b"):
        _write_proof(tmp_path, slug,
                     "import Mathlib\n"
                     f"namespace {PNS}\n"
                     f"theorem {slug} : True := by trivial\n"
                     f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    rows.sort(key=lambda r: r["file_order"])
    text = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    assert text is not None

    res = lib._commit_migrated_file(
        text, conn=conn, problem="p", workspace=tmp_path,
        target_path=tmp_path / tf, target_module="Library.P.Foo",
        ordered_slugs=["lem_a", "lem_b"], defs_names=[],
        whitelist=None,
        build_verifier=lambda _t: (True, ""))
    assert res.outcome == "success", res.failure_detail
    migrated = {r["slug"] for r in db.library_decls_for(conn, "p",
                                                        lifecycle="migrated")}
    assert migrated == {"lem_a", "lem_b"}
    # File written to disk.
    assert (tmp_path / tf).exists()
    # target_name backfilled to the Library FQ name.
    by = {r["slug"]: r for r in db.library_decls_for(conn, "p")}
    assert by["lem_a"]["target_name"] == "Library.P.Foo.lem_a"


def test_commit_rolls_back_on_gate_fail(conn, tmp_path):
    tf = "Library/P/Foo.lean"
    _seed_classified(conn, "lem_a", "True", tf, 0)
    _write_proof(tmp_path, "lem_a",
                 "import Mathlib\n"
                 f"namespace {PNS}\n"
                 "theorem lem_a : True := by trivial\n"
                 f"end {PNS}\n")
    rows = [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == tf and r["lifecycle"] == "classified"]
    text = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=tf,
        target_module="Library.P.Foo", rows=rows)
    res = lib._commit_migrated_file(
        text, conn=conn, problem="p", workspace=tmp_path,
        target_path=tmp_path / tf, target_module="Library.P.Foo",
        ordered_slugs=["lem_a"], defs_names=[], whitelist=None,
        build_verifier=lambda _t: (False, "boom"))
    assert res.outcome == "failed"
    # not advanced to migrated; file rolled back (build gate fails pre-write)
    assert db.library_decls_for(conn, "p", lifecycle="migrated") == []
