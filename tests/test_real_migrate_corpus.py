"""Real-build migrate corpus (backlog: migrate 機械路徑 shape-by-shape 硬化).

The offline mechanical-migrate suite (test_librarian_mechanical_migrate.py)
asserts TEXT properties of the assembled file — it cannot catch the class
"assembles fine but does not elaborate" (the `noncomputable section` /
relabel-artifact family that historically surfaced as live
librarian_migrate_build_failed STALLs, ~N per new problem shape).

This corpus closes that tier: each case seeds a realistic classified-file
shape, runs the SAME `_mechanical_migrate_file` the daemon runs, and then
BUILDS the assembled text against the real toolchain. Runs under the
`real_lake` marker (monthly real-lean CI + local opt-in via
ASTERISM_REAL_LAKE=1); adding a newly-discovered breaking shape = one more
`_Case` entry.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from Tooling.state import db
from Tooling.pipeline import librarian as lib

ROOT = Path(__file__).resolve().parents[1]
PNS = "Problems.p"


class _Case(NamedTuple):
    """One corpus shape: per-slug proof sources (or Defs decls) classified
    into a single Library file; `expect_in` = substrings the assembled text
    must carry (cheap pre-build sanity, keeps a red build diagnosable)."""
    id: str
    proofs: "dict[str, str]"          # slug -> L_<slug>.lean content
    defs_body: "str | None" = None    # Defs.lean content (defs_slugs case)
    defs_slugs: "tuple[str, ...]" = ()
    expect_in: "tuple[str, ...]" = ()


def _proof(body_decl: str, extra_header: str = "") -> str:
    return (f"import Mathlib\n{extra_header}"
            f"namespace {PNS}\n{body_decl}\nend {PNS}\n")


CORPUS: "list[_Case]" = [
    _Case(
        id="baseline_theorem",
        proofs={"lem_a": _proof("theorem lem_a : 1 + 1 = 2 := rfl")},
    ),
    _Case(
        # #72 (mayer_vietoris 2026-07-03): two universe-polymorphic sources
        # each declare `universe u`; replaying both is a hard error. The
        # assembled file must hoist ONE.
        id="universe_dedup",
        proofs={
            "u_a": ("import Mathlib\nuniverse u\n"
                    f"namespace {PNS}\ndef u_a : Type u := PUnit\nend {PNS}\n"),
            "u_b": ("import Mathlib\nuniverse u\n"
                    f"namespace {PNS}\ndef u_b : Type u := PUnit\nend {PNS}\n"),
        },
        expect_in=("universe u",),
    ),
    _Case(
        # BUG4 family: a data decl's `noncomputable` must survive relabel —
        # dropping it elaborates fine in probes that skip code-gen and only
        # explodes at the cold build ("mark it 'noncomputable'").
        id="noncomputable_data_def",
        proofs={"nc_val": _proof(
            "noncomputable def nc_val : Real := Real.pi")},
        expect_in=("noncomputable",),
    ),
    _Case(
        # Attribute + docstring travel: `@[simp]` and the docstring must
        # ride the slice (dropping @[simp] silently unregisters; a stray
        # docstring orphaned from its decl is a parse error).
        id="attr_and_docstring",
        proofs={"simp_lem": _proof(
            "/-- doubling once. -/\n"
            "@[simp] theorem simp_lem (n : Nat) : n + n = 2 * n := "
            "by omega")},
        expect_in=("@[simp]", "doubling once."),
    ),
    _Case(
        # Same-file sibling citation: lem_d cites lem_c by bare name (its
        # source imports the sibling's proofs module; the merged Library
        # file must resolve it bare, with the problem import stripped).
        id="same_file_sibling_cite",
        proofs={
            "lem_c": _proof("theorem lem_c : 1 + 1 = 2 := rfl"),
            "lem_d": _proof(
                "theorem lem_d : (2 : Nat) = 1 + 1 := lem_c.symm",
                extra_header=f"import {PNS}.proofs.L_lem_c\n"),
        },
        expect_in=("lem_c.symm",),
    ),
    _Case(
        # Defs.lean decl with a section `variable` in scope: the slice must
        # replay the variable line or the def's binder does not resolve.
        id="defs_section_variable",
        proofs={},
        defs_body=(f"import Mathlib\nnamespace {PNS}\n"
                   "variable (n : Nat)\n"
                   "def defs_val : Nat := n + 1\n"
                   f"end {PNS}\n"),
        defs_slugs=("defs_val",),
        expect_in=("variable (n : Nat)", "def defs_val"),
    ),
]


def _seed(conn, tmp_path: Path, case: _Case, target_file: str) -> list:
    (tmp_path / "Problems" / "p" / "proofs").mkdir(parents=True,
                                                   exist_ok=True)
    order = 0
    for slug, body in case.proofs.items():
        g = db.insert_goal(conn, problem="p", slug=slug,
                           lean_path=f"Problems/p/proofs/L_{slug}.lean",
                           statement="True", origin="backward",
                           kind="theorem")
        conn.execute("UPDATE goals SET status='proved' WHERE id=?", (g,))
        db.upsert_library_decl(conn, problem="p", slug=slug,
                               source_goal_id=g)
        db.set_library_verdict(conn, problem="p", slug=slug, verdict="keep")
        db.set_library_classification(
            conn, problem="p", slug=slug, target_file=target_file,
            target_name=None, file_order=order)
        (tmp_path / "Problems" / "p" / "proofs"
         / f"L_{slug}.lean").write_text(body, encoding="utf-8")
        order += 1
    if case.defs_body is not None:
        (tmp_path / "Problems" / "p" / "Defs.lean").write_text(
            case.defs_body, encoding="utf-8")
        for slug in case.defs_slugs:
            db.upsert_library_decl(conn, problem="p", slug=slug,
                                   source_goal_id=None)
            db.set_library_verdict(conn, problem="p", slug=slug,
                                   verdict="keep")
            db.set_library_classification(
                conn, problem="p", slug=slug, target_file=target_file,
                target_name=None, file_order=order)
            order += 1
    conn.commit()
    return [r for r in db.library_decls_for(conn, "p")
            if r["target_file"] == target_file
            and r["lifecycle"] == "classified"]


@pytest.mark.real_lake
@pytest.mark.parametrize("case", CORPUS, ids=[c.id for c in CORPUS])
def test_migrate_corpus_shape_builds(case: _Case, tmp_path: Path):
    conn = db.connect(":memory:")
    db.init_schema(conn)
    conn.execute("INSERT INTO problems (name, created_at,"
                 " bootstrap_done) VALUES ('p',?,1)", (db.now(),))
    conn.commit()
    target_file = "Library/Corpus/Shape.lean"
    rows = _seed(conn, tmp_path, case, target_file)
    assert rows, "seed produced no classified rows"

    text, holes, _asm = lib._mechanical_migrate_file(
        conn, problem="p", workspace=tmp_path, target_file=target_file,
        target_module="Library.Corpus.Shape", rows=rows)
    assert text is not None, f"{case.id}: mechanical migrate declined"
    assert holes == [], f"{case.id}: unexpected holes {holes}"
    for frag in case.expect_in:
        assert frag in text, (
            f"{case.id}: assembled text lost {frag!r}:\n{text}")

    # The tier this corpus exists for: the assembled text must ELABORATE
    # on the real toolchain (cold `lake env lean` against the repo
    # workspace — self-contained `import Mathlib` files by construction).
    from Tooling.quality.librarian.cleanup import _common as C
    ok, detail = C._build_file_copy_isolated(ROOT, text, timeout=300)
    assert ok, f"{case.id}: assembled file failed to build:\n{detail}"
