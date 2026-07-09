import Mathlib.Analysis.InnerProductSpace.PiL2
import Mathlib.GroupTheory.FreeGroup.Reduce

/-!
# Banach–Tarski definitions and free-group word lemmas

This file sets up the ambient Euclidean space `E := EuclideanSpace ℝ (Fin 3)` (i.e., ℝ³)
and equips the isometry group `E ≃ᵢ E` with a `SMul`/`MulAction` on `E`. It also contains
auxiliary lemmas about reduced words in free groups used in the equidecomposition argument.

## Main definitions

- `E` — the Euclidean space ℝ³.
- `SMul (E ≃ᵢ E) E` / `MulAction (E ≃ᵢ E) E` — the natural action of isometries on ℝ³.

## Main statements

- `reduce_cons_head_of_reduced` — the head of `FreeGroup.reduce (x :: L)` is `x` iff `L`
  does not begin with the inverse of `x` (given `L` is already reduced).
- `head_inv_mul_iff` — the head of the reduced word for `i⁻¹ * w` is `(i, false)` iff
  `toWord w` does not start with `(i, true)`.
- `tail_of_reduced_is_reduced` — the tail of a reduced word is itself reduced.
- `cons_head_ne_inv` — in a reduced word `x :: M`, the head of `M` is not the inverse of
  `x`.
-/

namespace Library.Geometry.BanachTarski.Defs

/-- The ambient Euclidean space ℝ³ used in the Banach–Tarski statement. -/
abbrev E : Type := EuclideanSpace ℝ (Fin 3)

/-- The self-isometry group of `E = ℝ³` acts on `E` by function application.
`Mathlib` provides `Group (α ≃ᵢ α)`; this `SMul` instance bridges to `Equidecomp`,
whose `IsDecompOn` predicate requires `[SMul G X]`. -/
noncomputable instance : SMul (E ≃ᵢ E) E := ⟨fun g x => g x⟩

/-- The `MulAction` of `E ≃ᵢ E` on `E`, compatible with the `SMul` instance above. -/
noncomputable instance : MulAction (E ≃ᵢ E) E where
  one_smul _ := rfl
  mul_smul _ _ _ := rfl

/-- The head of `FreeGroup.reduce (x :: L)` is `x` if and only if `L` does not begin with
the inverse of `x`, provided `L` is already reduced. -/
theorem reduce_cons_head_of_reduced {α : Type*} [DecidableEq α]
    (x : α × Bool) (L : List (α × Bool)) (hL : FreeGroup.reduce L = L) :
    (FreeGroup.reduce (x :: L)).head? = some x ↔ L.head? ≠ some (x.1, !x.2) := by
  rw [FreeGroup.reduce.cons, hL]
  cases L with
  | nil => simp
  | cons hd tl =>
    have h_reduced : tl.head? ≠ some (hd.1, !hd.2) := by
      intro hcontra
      rw [List.head?_eq_some_iff] at hcontra
      obtain ⟨rest, hrest⟩ := hcontra
      subst hrest
      obtain ⟨c, e⟩ := hd
      have hstep : FreeGroup.Red.Step ((c, e) :: (c, !e) :: rest) rest :=
        @FreeGroup.Red.Step.not α [] rest c e
      have heq := FreeGroup.reduce.eq_of_red hstep.to_red
      simp only at hL heq
      rw [hL] at heq
      obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := rest))
      have hlen := congrArg List.length heq
      simp only [List.length_cons] at hlen
      omega
    obtain ⟨a, b⟩ := x
    obtain ⟨c, d⟩ := hd
    simp only [List.head?_cons]
    split_ifs with hcond
    · obtain ⟨rfl, rfl⟩ := hcond
      simpa [Bool.not_not] using h_reduced
    · simp only [List.head?_cons, Option.some.injEq, Prod.mk.injEq, true_iff, ne_eq, not_and]
      intro hc hd2
      exact hcond ⟨hc.symm, by rw [hd2, Bool.not_not]⟩

/-- The head of the reduced word for `(FreeGroup.of i)⁻¹ * w` equals `(i, false)` if and
only if the head of `FreeGroup.toWord w` is not `(i, true)`.

In other words, prepending the inverse generator `i⁻¹` does not cancel with the leading
letter of `w` precisely when that letter is not `i` itself. -/
theorem head_inv_mul_iff {α : Type*} [DecidableEq α] (i : α) (w : FreeGroup α) :
    (FreeGroup.toWord ((FreeGroup.of i)⁻¹ * w)).head? = some (i, false)
      ↔ (FreeGroup.toWord w).head? ≠ some (i, true) := by
  have hmul : FreeGroup.toWord ((FreeGroup.of i)⁻¹ * w)
      = FreeGroup.reduce ((i, false) :: FreeGroup.toWord w) := by
    have hinv : (FreeGroup.of i)⁻¹ = FreeGroup.mk [(i, false)] := by
      rw [show (FreeGroup.of i) = FreeGroup.mk [(i, true)] from rfl, FreeGroup.inv_mk]; rfl
    conv_lhs => rw [hinv, ← FreeGroup.mk_toWord (x := w), FreeGroup.mul_mk]
    rw [FreeGroup.toWord_mk]; rfl
  rw [hmul]
  have h := reduce_cons_head_of_reduced (i, false) (FreeGroup.toWord w)
    (FreeGroup.reduce_toWord w)
  simpa using h

/-- The tail of a reduced word is itself reduced.

If `FreeGroup.reduce (x :: M) = x :: M`, then `FreeGroup.reduce M = M`. -/
theorem tail_of_reduced_is_reduced {α : Type*} [DecidableEq α]
    (x : α × Bool) (M : List (α × Bool))
    (h : FreeGroup.reduce (x :: M) = x :: M) :
    FreeGroup.reduce M = M := by
  exact ((FreeGroup.IsReduced.of_reduce_eq h).infix ⟨[x], [], by simp⟩).reduce_eq

/-- In a reduced word `x :: M`, the head of `M` is not the inverse of `x`.

If `FreeGroup.reduce (x :: M) = x :: M` and `M` is non-empty, then
`M.head? ≠ some (x.1, !x.2)`. -/
theorem cons_head_ne_inv (x : Fin 2 × Bool) (M : List (Fin 2 × Bool))
    (hred : FreeGroup.reduce (x :: M) = x :: M) (_hne : M ≠ []) :
    M.head? ≠ some (x.1, !x.2) := by
  intro hcontra
  rw [List.head?_eq_some_iff] at hcontra
  obtain ⟨rest, hrest⟩ := hcontra
  subst hrest
  obtain ⟨c, e⟩ := x
  simp only at hred
  have hstep : FreeGroup.Red.Step ((c, e) :: (c, !e) :: rest) rest :=
    @FreeGroup.Red.Step.not (Fin 2) [] rest c e
  have heq := FreeGroup.reduce.eq_of_red hstep.to_red
  simp only at heq
  rw [hred] at heq
  obtain ⟨n, hn⟩ := FreeGroup.Red.length (FreeGroup.reduce.red (L := rest))
  have hlen := congrArg List.length heq
  simp only [List.length_cons] at hlen hn
  omega

end Library.Geometry.BanachTarski.Defs
