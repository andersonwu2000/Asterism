"""Usage DAG (inventory.usage_graph) + intra-file topological ordering
(librarian._toposort_intra_file / commit_classify).

Root cause 2: file/decl order must follow the proof-term *usage* DAG, not
the decomposition DAG — a cited sibling must be emitted before its user or
Lean reports an unknown identifier. Pure offline; no gateway/build.
"""
from __future__ import annotations

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib
from Tooling.quality.librarian import inventory as inv

PNS = "Problems.p"


def _proofs(workspace):
    p = workspace / "Problems" / "p" / "proofs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _alias(workspace, slug, sid):
    (_proofs(workspace) / f"L_{slug}.lean").write_text(
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"import {PNS}.proofs._strategy_s{sid}\n"
        f"namespace {PNS}\n"
        f"def {slug} := @{PNS}.s{sid}\n"
        f"end {PNS}\n", encoding="utf-8")


def _strategy(workspace, sid, *, uses):
    body = ["import Mathlib", f"import {PNS}.Defs"]
    body += [f"import {PNS}.proofs.L_{u}" for u in uses]
    body += [f"namespace {PNS}", f"theorem s{sid} : True := by trivial",
             f"end {PNS}"]
    (_proofs(workspace) / f"_strategy_s{sid}.lean").write_text(
        "\n".join(body) + "\n", encoding="utf-8")


# --- usage_graph: alias → strategy → sibling resolution ---

def test_usage_graph_resolves_through_alias_and_strategy(tmp_path):
    # X's alias imports _strategy_s100; that strategy imports L_Y → edge X→Y.
    _alias(tmp_path, "x", 100)
    _strategy(tmp_path, 100, uses=["y"])
    _alias(tmp_path, "y", 200)
    _strategy(tmp_path, 200, uses=[])
    g = inv.usage_graph(tmp_path, "p", {"x", "y"})
    assert g["x"] == {"y"}
    assert g["y"] == set()


def test_usage_graph_recurses_nested_strategies(tmp_path):
    # X → _strategy_s1 → _strategy_s2 → L_Z : the nested strategy import must
    # still attribute Z as a direct usage dep of X.
    _alias(tmp_path, "x", 1)
    (_proofs(tmp_path) / "_strategy_s1.lean").write_text(
        "import Mathlib\n"
        f"import {PNS}.proofs._strategy_s2\n"
        f"namespace {PNS}\ntheorem s1 : True := by trivial\nend {PNS}\n",
        encoding="utf-8")
    _strategy(tmp_path, 2, uses=["z"])
    _alias(tmp_path, "z", 3)
    _strategy(tmp_path, 3, uses=[])
    g = inv.usage_graph(tmp_path, "p", {"x", "z"})
    assert g["x"] == {"z"}


def test_usage_graph_drops_edges_outside_slug_set(tmp_path):
    # X uses Y, but Y isn't in the placed set → no edge (Y won't order a file).
    _alias(tmp_path, "x", 10)
    _strategy(tmp_path, 10, uses=["y"])
    g = inv.usage_graph(tmp_path, "p", {"x"})
    assert g["x"] == set()


def test_usage_graph_missing_file_is_empty(tmp_path):
    # No proof files on disk → best-effort empty graph, never raises.
    g = inv.usage_graph(tmp_path, "p", {"x", "y"})
    assert g == {"x": set(), "y": set()}


def test_usage_graph_remaps_merged_sibling(tmp_path):
    # X's proof imports L_y_alias, but y_alias was dedup-merged into the kept
    # canonical `y` (and dropped, so not placed). The usage edge must remap to
    # `y` — the real Jordan pushforward_d_eq_alias → pushforward_d_eq case.
    _alias(tmp_path, "x", 100)
    _strategy(tmp_path, 100, uses=["y_alias"])
    # without remap: y_alias not placed → edge lost
    assert inv.usage_graph(tmp_path, "p", {"x", "y"})["x"] == set()
    # with remap: y_alias → y → edge X→y
    g = inv.usage_graph(tmp_path, "p", {"x", "y"},
                        alias_map={"y_alias": "y"})
    assert g["x"] == {"y"}


def test_usage_graph_folds_self_merged_sibling_transitive_deps(tmp_path):
    # x's proof cites `m`, but `m` was dedup-merged INTO x itself (self-merge),
    # so `m` is dropped and x's migrated body must INLINE m's proof — which cites
    # the cross-file kept sibling `z`. The edge x→z exists ONLY through the
    # inlined self-merged sibling and must not be lost (real Jordan:
    # block_jordan_basis_exists cites assemble_block_jordan_strong (merge→itself)
    # whose proof uses extended_jordan_family_strong in another file).
    _alias(tmp_path, "x", 100)
    _strategy(tmp_path, 100, uses=["m"])
    _alias(tmp_path, "m", 200)
    _strategy(tmp_path, 200, uses=["z"])
    _alias(tmp_path, "z", 300)
    _strategy(tmp_path, 300, uses=[])
    # Pre-fix: m→x self-edge dropped, m's proof never walked → edge x→z lost.
    g = inv.usage_graph(tmp_path, "p", {"x", "z"}, alias_map={"m": "x"})
    assert g["x"] == {"z"}
    # z, having no self-merged sibling, stays a leaf.
    assert g["z"] == set()


def test_usage_graph_self_merge_recursion_terminates(tmp_path):
    # Pathological: m merges into x and m's proof cites x's own L_ (cycle).
    # seen_mods must bound the walk — no infinite recursion, no crash.
    _alias(tmp_path, "x", 100)
    _strategy(tmp_path, 100, uses=["m"])
    _alias(tmp_path, "m", 200)
    _strategy(tmp_path, 200, uses=["x"])
    g = inv.usage_graph(tmp_path, "p", {"x"}, alias_map={"m": "x"})
    assert g["x"] == set()


def test_usage_graph_root_source_reads_root_lean(tmp_path):
    # The root decl's proof is Root.lean (an alias to a strategy), not
    # proofs/L_main.lean. Without root_source its citations are invisible
    # (Main.lean would look dependency-free → mis-ordered before the files it
    # imports); with it, the strategy walk finds the cited sibling.
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Root.lean").write_text(
        "import Mathlib\n"
        f"import {PNS}.Defs\n"
        f"import {PNS}.proofs._strategy_s9\n"
        f"namespace {PNS}\n"
        f"def main := @{PNS}.s9\n"
        f"end {PNS}\n", encoding="utf-8")
    _strategy(tmp_path, 9, uses=["dep"])
    _alias(tmp_path, "dep", 10)
    _strategy(tmp_path, 10, uses=[])
    # without root_source: no L_main.lean → root looks dependency-free
    assert inv.usage_graph(tmp_path, "p", {"main", "dep"})["main"] == set()
    # with root_source: Root.lean → strategy s9 → L_dep → edge main→dep
    g = inv.usage_graph(tmp_path, "p", {"main", "dep"},
                        root_source=("main", str(pdir / "Root.lean")))
    assert g["main"] == {"dep"}


def test_referenced_slugs_root_source_reads_root_lean(tmp_path):
    # Same root-source fix for the redirect-table scanner.
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "Root.lean").write_text(
        "import Mathlib\n"
        f"import {PNS}.proofs._strategy_s9\n"
        f"namespace {PNS}\n"
        f"def main := @{PNS}.s9\n"
        f"end {PNS}\n", encoding="utf-8")
    _strategy(tmp_path, 9, uses=["dep"])
    assert inv.referenced_slugs(tmp_path, "p", ["main"])["main"] == set()
    r = inv.referenced_slugs(tmp_path, "p", ["main"],
                             root_source=("main", str(pdir / "Root.lean")))
    assert "dep" in r["main"]


def test_merge_alias_map_resolves_chain(conn, tmp_path):
    # a merges into b, b merges into c (kept) → alias map a→c, b→c.
    for s in ("a", "b", "c"):
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
    db.set_library_verdict(conn, problem="p", slug="c", verdict="keep")
    db.set_library_verdict(conn, problem="p", slug="b", verdict="merge",
                           citation="c")
    db.set_library_verdict(conn, problem="p", slug="a", verdict="merge",
                           citation="b")
    amap = lib._merge_alias_map(conn, "p")
    assert amap == {"a": "c", "b": "c"}


# --- _toposort_intra_file: stable, usage-respecting ---

def test_toposort_places_dep_before_user():
    # input order [user, dep] but user uses dep → dep must come first.
    out = lib._toposort_intra_file(["user", "dep"], {"user": {"dep"}})
    assert out == ["dep", "user"]


def test_toposort_stable_when_independent():
    # no usage edges → original order preserved.
    out = lib._toposort_intra_file(["a", "b", "c"], {})
    assert out == ["a", "b", "c"]


def test_toposort_chain():
    # c uses b, b uses a → a, b, c regardless of input order.
    out = lib._toposort_intra_file(
        ["c", "b", "a"], {"c": {"b"}, "b": {"a"}})
    assert out == ["a", "b", "c"]


def test_toposort_cycle_falls_back_to_input_order():
    # a↔b cycle (shouldn't happen) → no crash, leftovers in input order.
    out = lib._toposort_intra_file(["a", "b"], {"a": {"b"}, "b": {"a"}})
    assert set(out) == {"a", "b"} and len(out) == 2


# --- commit_classify end-to-end: file_order reflects usage ---

@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, manifest_path, created_at, "
              "bootstrap_done) VALUES ('p','',?,1)", (db.now(),))
    c.commit()
    return c


def test_merge_file_sccs_collapses_cycle():
    # A<->B mutually import (a usage SCC) -> merged to the bigger file (A, 3
    # decls); the acyclic singleton C is left untouched.
    fgraph = {"A.lean": {"B.lean"}, "B.lean": {"A.lean", "C.lean"},
              "C.lean": set()}
    decls_in = {"A.lean": ["a1", "a2", "a3"], "B.lean": ["b1"],
                "C.lean": ["c1"]}
    canon = lib._merge_file_sccs(fgraph, decls_in)
    assert canon == {"A.lean": "A.lean", "B.lean": "A.lean"}


def test_commit_classify_merges_cyclic_files(conn, tmp_path):
    # `foo` (in Foo.lean) cites `bar` (in Bar.lean) and vice versa — a
    # file-level usage cycle the agent split across two files. commit_classify
    # must merge them into ONE file (else circular import, un-orderable).
    for s in ("foo", "bar"):
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
        db.set_library_verdict(conn, problem="p", slug=s, verdict="keep")
    _alias(tmp_path, "foo", 100); _strategy(tmp_path, 100, uses=["bar"])
    _alias(tmp_path, "bar", 200); _strategy(tmp_path, 200, uses=["foo"])
    plan = lib.ClassifyPlan([
        lib.ClassifyFile("Library/P/Foo.lean", [], ["foo"]),
        lib.ClassifyFile("Library/P/Bar.lean", [], ["bar"]),
    ])
    lib.commit_classify(conn, "p", plan, tmp_path)
    rows = db.library_decls_for(conn, "p", lifecycle="classified")
    files = {r["target_file"] for r in rows}
    assert len(files) == 1                      # merged into one file
    assert {r["slug"] for r in rows} == {"foo", "bar"}   # both decls kept


def test_commit_classify_reorders_by_usage(conn, tmp_path):
    # `user` cites `dep`; the agent listed them user-first. After commit the
    # persisted file_order must put dep (0) before user (1).
    for s in ("dep", "user"):
        db.upsert_library_decl(conn, problem="p", slug=s, source_goal_id=None)
        db.set_library_verdict(conn, problem="p", slug=s, verdict="keep")
    _alias(tmp_path, "user", 100)
    _strategy(tmp_path, 100, uses=["dep"])
    _alias(tmp_path, "dep", 200)
    _strategy(tmp_path, 200, uses=[])
    plan = lib.ClassifyPlan([
        lib.ClassifyFile("Library/P/Foo.lean", [], ["user", "dep"]),
    ])
    lib.commit_classify(conn, "p", plan, tmp_path)
    by = {r["slug"]: r["file_order"]
          for r in db.library_decls_for(conn, "p", lifecycle="classified")}
    assert by["dep"] == 0
    assert by["user"] == 1
