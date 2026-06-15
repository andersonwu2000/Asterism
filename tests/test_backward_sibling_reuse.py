"""`_partition_sibling_reuse` — convert a re-declared equivalent sibling
into a citation instead of forking a `_2` duplicate (agent_feedback T8 /
91-92,110).

Rule: a declared `new_<slug>.lean` whose slug names an existing
non-ancestor, non-parent sibling with a verbatim-equivalent theorem head
is DROPPED and replaced by an `import Problems.<p>.proofs.L_<slug>`
citation; everything else stays for the `_2` collision resolver.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.pipeline.backward import (
    _partition_sibling_reuse,
    _partition_dedupe_reuse,
    _apply_reuse_rewrites,
)
from Tooling.quality.dedupe import CanonicalMatch
from Tooling.state import db


@pytest.fixture
def conn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> sqlite3.Connection:
    monkeypatch.chdir(tmp_path)
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES ('p', 'Problems/p/Manifest.md', ?)",
        (db.now(),),
    )
    c.commit()
    return c


def _write_goal_file(workspace: Path, slug: str, head: str) -> str:
    """Write a proofs/L_<slug>.lean with `theorem <slug> <head> := by
    sorry` and return the workspace-relative path."""
    rel = f"Problems/p/proofs/L_{slug}.lean"
    p = workspace / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"import Mathlib\n\nnamespace Problems.p\n\n"
        f"theorem {slug} {head} := by sorry\n\n"
        f"end Problems.p\n",
        encoding="utf-8",
    )
    return rel


def _insert_goal(conn: sqlite3.Connection, slug: str, *, status: str,
                 lean_path: str) -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug, lean_path=lean_path,
        statement="T", origin="backward", status=status,
    )


def _declared(tmp_path: Path, slug: str, head: str) -> Path:
    """Write an attempts-dir `new_<slug>.lean` declaration and return it."""
    d = tmp_path / "attempts"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"new_{slug}.lean"
    p.write_text(
        f"namespace Problems.p\ntheorem {slug} {head} := by sorry\n"
        f"end Problems.p\n",
        encoding="utf-8",
    )
    return p


def test_equivalent_redeclaration_becomes_citation(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Declared slug matches an existing sibling with the SAME head →
    dropped + cited."""
    rel = _write_goal_file(tmp_path, "helper", "(n : Nat) : n = n")
    _insert_goal(conn, "helper", status="open", lean_path=rel)
    ns = _declared(tmp_path, "helper", "(n : Nat) : n = n")
    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=999, workspace=tmp_path,
        sub_meta=[("helper", ns)], existing_slugs={"helper"},
        ancestor_slugs={},
    )
    assert kept == []
    assert reuse_imports == ["import Problems.p.proofs.L_helper"]
    assert dropped == [ns]


def test_different_statement_same_slug_is_kept(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Same slug, DIFFERENT head → genuine name collision, kept for the
    `_2` resolver (NOT silently aliased onto an unrelated lemma)."""
    rel = _write_goal_file(tmp_path, "helper", "(n : Nat) : n = n")
    _insert_goal(conn, "helper", status="open", lean_path=rel)
    ns = _declared(tmp_path, "helper", "(m : Int) : m + 0 = m")
    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=999, workspace=tmp_path,
        sub_meta=[("helper", ns)], existing_slugs={"helper"},
        ancestor_slugs={},
    )
    assert kept == [("helper", ns)]
    assert reuse_imports == []
    assert dropped == []


def test_novel_slug_is_kept(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A slug not naming any existing goal is a real new sub-goal."""
    ns = _declared(tmp_path, "brand_new", "(n : Nat) : n = n")
    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=999, workspace=tmp_path,
        sub_meta=[("brand_new", ns)], existing_slugs=set(),
        ancestor_slugs={},
    )
    assert kept == [("brand_new", ns)]
    assert reuse_imports == []
    assert dropped == []


def test_ancestor_slug_is_never_cited(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A slug naming a strict ancestor is skipped (citing it would be an
    import cycle) — left for the `_2` resolver even if head-equivalent."""
    rel = _write_goal_file(tmp_path, "anc", "(n : Nat) : n = n")
    _insert_goal(conn, "anc", status="open", lean_path=rel)
    ns = _declared(tmp_path, "anc", "(n : Nat) : n = n")
    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=999, workspace=tmp_path,
        sub_meta=[("anc", ns)], existing_slugs={"anc"},
        ancestor_slugs={"anc": rel},
    )
    assert kept == [("anc", ns)]
    assert reuse_imports == []
    assert dropped == []


def test_parent_own_slug_is_never_cited(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """The parent goal being decomposed is excluded (id != goal_id), so a
    sub-goal re-stating the parent's own slug is NOT cited (self-cycle);
    the dedupe `no_progress` tier handles that case downstream."""
    rel = _write_goal_file(tmp_path, "parent", "(n : Nat) : n = n")
    parent_id = _insert_goal(conn, "parent", status="attempting",
                             lean_path=rel)
    ns = _declared(tmp_path, "parent", "(n : Nat) : n = n")
    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=parent_id, workspace=tmp_path,
        sub_meta=[("parent", ns)], existing_slugs={"parent"},
        ancestor_slugs={},
    )
    assert kept == [("parent", ns)]
    assert reuse_imports == []
    assert dropped == []


def test_shelved_sibling_redeclaration_becomes_citation(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """The motivating T8 case: re-declaring a cascade-SHELVED sibling
    verbatim is converted to a citation (the cite gate then REVIVES it),
    instead of forking a `_2` duplicate that can never re-register."""
    rel = _write_goal_file(tmp_path, "slice_normal_contdiffon",
                           "(f : Nat) : f = f")
    _insert_goal(conn, "slice_normal_contdiffon", status="shelved",
                 lean_path=rel)
    ns = _declared(tmp_path, "slice_normal_contdiffon", "(f : Nat) : f = f")
    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=999, workspace=tmp_path,
        sub_meta=[("slice_normal_contdiffon", ns)],
        existing_slugs={"slice_normal_contdiffon"}, ancestor_slugs={},
    )
    assert kept == []
    assert reuse_imports == [
        "import Problems.p.proofs.L_slice_normal_contdiffon"]
    assert dropped == [ns]


def test_mixed_batch_partitions_correctly(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A batch with one reuse + one novel + one different-statement
    collision partitions cleanly."""
    rel = _write_goal_file(tmp_path, "reused", "(n : Nat) : n = n")
    _insert_goal(conn, "reused", status="shelved", lean_path=rel)
    rel2 = _write_goal_file(tmp_path, "clash", "(n : Nat) : n = n")
    _insert_goal(conn, "clash", status="open", lean_path=rel2)

    ns_reuse = _declared(tmp_path, "reused", "(n : Nat) : n = n")
    ns_novel = _declared(tmp_path, "fresh", "(n : Nat) : n + 0 = n")
    ns_clash = _declared(tmp_path, "clash", "(m : Int) : m = m")  # diff head

    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=999, workspace=tmp_path,
        sub_meta=[("reused", ns_reuse), ("fresh", ns_novel),
                  ("clash", ns_clash)],
        existing_slugs={"reused", "clash"}, ancestor_slugs={},
    )
    assert ("fresh", ns_novel) in kept
    assert ("clash", ns_clash) in kept
    assert ("reused", ns_reuse) not in kept
    assert reuse_imports == ["import Problems.p.proofs.L_reused"]
    assert dropped == [ns_reuse]


def test_dead_sibling_redeclaration_is_kept_not_cited(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A re-declared DEAD sibling (wrong-as-stated) must NOT be cited —
    the cite-gate rejects dead (6fc6ff4), which would abort the strategy.
    Keep it for the `_2` resolver so the re-declaration becomes a fresh
    re-statement under this strategy instead."""
    rel = _write_goal_file(tmp_path, "wrong", "(n : Nat) : n = n")
    _insert_goal(conn, "wrong", status="dead", lean_path=rel)
    ns = _declared(tmp_path, "wrong", "(n : Nat) : n = n")
    kept, reuse_imports, dropped = _partition_sibling_reuse(
        conn, problem="p", goal_id=999, workspace=tmp_path,
        sub_meta=[("wrong", ns)], existing_slugs={"wrong"},
        ancestor_slugs={},
    )
    assert kept == [("wrong", ns)]
    assert reuse_imports == []
    assert dropped == []


# ---------------------------------------------------------------------
# #2 dedupe-reuse: a DIFFERENT-named but signature-equivalent twin
# (dedupe kind="reuse") → extract + patch rewrite (Y → twin theorem name).
# ---------------------------------------------------------------------

def test_partition_dedupe_reuse_extracts_reuse_match(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A `reuse` match is dropped from the kept sub-goals and recorded as a
    (slug, twin_theorem_name, twin_module) rewrite; a None / non-reuse
    match stays."""
    rel = _write_goal_file(tmp_path, "twin_x", "(a : Nat) : a = a")
    x = _insert_goal(conn, "twin_x", status="open", lean_path=rel)
    s_reuse = _declared(tmp_path, "dup", "(a : Nat) : a = a")
    s_novel = _declared(tmp_path, "novel", "(b : Nat) : b + 0 = b")
    kept_meta, kept_canon, rewrites = _partition_dedupe_reuse(
        conn, problem="p", workspace=tmp_path,
        sub_meta=[("dup", s_reuse), ("novel", s_novel)],
        canonical_for=[CanonicalMatch(goal_id=x, kind="reuse"), None],
    )
    assert [s for s, _ in kept_meta] == ["novel"]
    assert kept_canon == [None]
    assert rewrites == [("dup", "twin_x", "Problems.p.proofs.L_twin_x")]


def test_partition_dedupe_reuse_keeps_non_reuse(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """alias / disproved / no_progress matches are NOT extracted here
    (they're handled by their own code paths) — only `reuse` is."""
    s = _declared(tmp_path, "a", ": T")
    kept_meta, kept_canon, rewrites = _partition_dedupe_reuse(
        conn, problem="p", workspace=tmp_path,
        sub_meta=[("a", s)],
        canonical_for=[CanonicalMatch(goal_id=5, kind="alias")],
    )
    assert kept_meta == [("a", s)]
    assert kept_canon == [CanonicalMatch(goal_id=5, kind="alias")]
    assert rewrites == []


def test_apply_reuse_rewrites_renames_value_ref_and_imports() -> None:
    """The bare slug VALUE reference is swapped for the twin theorem name
    and the twin module imported; the `h_<slug>` hypothesis name (no word
    boundary inside) is left intact."""
    patch = (
        "import Mathlib\n"
        "namespace Problems.p\n"
        "theorem s1 : T := by\n"
        "  have h_dup := dup arg\n"
        "  exact c h_dup\n"
        "end Problems.p\n"
    )
    out = _apply_reuse_rewrites(
        patch, [("dup", "real_twin", "Problems.p.proofs.L_real_twin")])
    assert "have h_dup := real_twin arg" in out   # value ref rewritten
    assert "import Problems.p.proofs.L_real_twin" in out
    assert "exact c h_dup" in out                 # hypothesis name intact
    assert "dup arg" not in out                   # old bare ref gone
