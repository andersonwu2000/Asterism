"""The audit type-invariance gate's safe-generalization relaxation.

`_type_generalizes` decides whether a `#check @decl` type change is *only* a
drop-unused-hypothesis generalization (admissible) versus any other change
(rejected — a changed conclusion or altered/added hypothesis must never slip
through). These are the safety invariants; they gate whether cleanup may delete
an unused hypothesis binder rather than STALL on its `unused variable` lint.
"""
from __future__ import annotations

from Tooling.quality.librarian.cleanup.audit import (
    _arrow_segments, _is_subsequence, _split_toplevel, _type_generalizes,
)


# real `#check @` shapes captured from Lean (∀ prefix, arrow-chain body).
FOO = "∀ {r : ℝ}, 0 < r → r < 1 → r < 2"
FOO_DROP_HR = "∀ {r : ℝ}, r < 1 → r < 2"                       # dropped `0 < r`
BAZ = ("∀ {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}, Continuous γ → 0 < r → "
       "(∀ t ∈ Set.Icc 0 1, r < dist (γ t) z) → Continuous γ")
BAZ_DROP_HR = ("∀ {γ : ℝ → ℂ} {z : ℂ} {r : ℝ}, Continuous γ → "
               "(∀ t ∈ Set.Icc 0 1, r < dist (γ t) z) → Continuous γ")


def test_split_toplevel_is_bracket_aware() -> None:
    # the comma / arrow inside `(∀ t ∈ S, …)` must NOT split
    assert _split_toplevel("a → (∀ t ∈ S, p t) → c", "→") == \
        ["a ", " (∀ t ∈ S, p t) ", " c"]
    assert _split_toplevel("∀ {r : ℝ}, 0 < r → c", ",") == \
        ["∀ {r : ℝ}", " 0 < r → c"]


def test_arrow_segments_splits_prefix_and_body() -> None:
    prefix, segs = _arrow_segments(FOO)
    assert prefix == "∀ {r : ℝ}"
    assert segs == ["0 < r", "r < 1", "r < 2"]
    # bracketed hypothesis stays one segment
    _p, bsegs = _arrow_segments(BAZ)
    assert bsegs[2] == "(∀ t ∈ Set.Icc 0 1, r < dist (γ t) z)"
    assert bsegs[-1] == "Continuous γ"


def test_is_subsequence() -> None:
    assert _is_subsequence(["a", "c"], ["a", "b", "c"])
    assert not _is_subsequence(["c", "a"], ["a", "b", "c"])     # order matters


def test_generalizes_admits_dropped_hypothesis() -> None:
    assert _type_generalizes(FOO, FOO_DROP_HR)
    assert _type_generalizes(BAZ, BAZ_DROP_HR)                  # bracket-aware


def test_generalizes_rejects_weakened_conclusion() -> None:
    # conclusion P ∧ Q silently narrowed to P is NOT a generalization
    old = "∀ {p : Prop}, h → p ∧ p"
    new = "∀ {p : Prop}, h → p"
    assert not _type_generalizes(old, new)


def test_generalizes_rejects_added_hypothesis() -> None:
    assert not _type_generalizes(FOO_DROP_HR, FOO)             # added, not dropped


def test_generalizes_rejects_changed_binders() -> None:
    assert not _type_generalizes(FOO, "∀ {r : ℕ}, r < 1 → r < 2")


def test_generalizes_rejects_identity() -> None:
    assert not _type_generalizes(FOO, FOO)                     # nothing dropped


def test_generalizes_rejects_altered_hypothesis() -> None:
    # same arity, but a surviving hypothesis is different → not a subsequence
    old = "∀ {r : ℝ}, 0 < r → r < 1 → r < 2"
    new = "∀ {r : ℝ}, 0 < r → r < 5 → r < 2"
    assert not _type_generalizes(old, new)
