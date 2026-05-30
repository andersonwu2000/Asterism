"""Regression: the dedup verify slug universe must include Defs.lean decls.

The dedup agent is told to judge Defs declarations too (a `def` can reinvent
a mathlib notion — prompts/librarian/dedup.md), and compile_librarian_context
shows them in Context.md. If the verify slug set is built only from proved
goals, every verdict on a Defs decl is rejected as "not in inventory" and the
whole batch fails. Caught live on the first clean SG dedup run (2026-05-31):
`librarian_verify_failed: Collinear: not in this problem's inventory`.

These tests pin `dedup_slug_universe` — the single source of that union that
both the verify slug set and the candidate-row upsert derive from — by
constructing an Inventory directly (no DB / no file-scan dependency).
"""
from Tooling.quality.librarian.inventory import Inventory, InvDecl
from Tooling.pipeline import librarian as lib


def _decl(slug):
    return InvDecl(goal_id=1, slug=slug, status="proved", kind="sub",
                   origin="backward", lean_path=f"proofs/L_{slug}.lean")


def test_universe_unions_goals_and_defs():
    inv = Inventory(
        problem="p",
        decls=[_decl("root_thm"), _decl("lemma_a")],
        defs_decls=["Collinear"],
    )
    universe = lib.dedup_slug_universe(inv)
    assert universe == {"root_thm", "lemma_a", "Collinear"}


def test_verify_accepts_verdict_on_defs_decl():
    """A cite-mathlib verdict on a Defs decl passes verify once the
    universe is built correctly — the exact case that failed live."""
    inv = Inventory(problem="p", decls=[_decl("lemma_a")],
                    defs_decls=["Collinear"])
    universe = lib.dedup_slug_universe(inv)
    verdicts, err = lib.parse_dedup(
        '[{"slug":"Collinear","verdict":"cite-mathlib",'
        '"mathlib_name":"Collinear"}]'
    )
    assert err == ""
    assert lib.verify_dedup(verdicts, universe) == ""


def test_defs_free_problem_universe_is_just_goals():
    inv = Inventory(problem="p", decls=[_decl("root_thm"), _decl("lemma_a")],
                    defs_decls=[])
    assert lib.dedup_slug_universe(inv) == {"root_thm", "lemma_a"}
