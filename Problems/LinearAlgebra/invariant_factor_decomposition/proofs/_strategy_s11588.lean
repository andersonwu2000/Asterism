import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs
import Problems.LinearAlgebra.invariant_factor_decomposition.proofs.L_sorted_enum

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- Direct construction (was: circular `pad_and_place`). Only the sorting is delegated.
--   `sorted_enum` (sub-goal): enumerate J in weight-monotone order, `e : Fin #J ≃ J`
--     with `w ∘ e` monotone — strictly smaller (no Fin-r / placement structure).
-- patch builds the witnesses explicitly: place j at `r - #J + e.symm j` (bottom block),
-- pad positions below `r - #J` with 0.  Monotone: padding 0 ≤ sorted tail, tail monotone
-- via `he`.  The five conjuncts are then Fin/Nat bookkeeping (omega + e.apply_symm_apply).
theorem s11588 {J : Type*} [Fintype J] (w : J → ℕ) (r : ℕ)
    (hr : Fintype.card J ≤ r) :
    ∃ (cvec : Fin r → ℕ) (pos : J → Fin r),
      Monotone cvec ∧
      Function.Injective pos ∧
      (∀ j, cvec (pos j) = w j) ∧
      (∀ (k : Fin r), (∀ j, pos j ≠ k) → cvec k = 0) ∧
      (∀ (k : Fin r), r - Fintype.card J ≤ (k : ℕ) → ∃ j, pos j = k)  := by
  set n := Fintype.card J with hn
  have h_sorted : ∃ (e : Fin n ≃ J), Monotone (w ∘ e) := sorted_enum w

  obtain ⟨e, he⟩ := h_sorted

  refine ⟨fun k => if h : (k : ℕ) < r - n then 0 else w (e ⟨(k : ℕ) - (r - n), by omega⟩),
          fun j => ⟨r - n + (e.symm j : ℕ), by omega⟩, ?_, ?_, ?_, ?_, ?_⟩
  · intro a b hab
    have hab' : (a : ℕ) ≤ (b : ℕ) := hab
    by_cases ha : (a : ℕ) < r - n
    · simp only [dif_pos ha]; exact Nat.zero_le _
    · have hb : ¬ (b : ℕ) < r - n := by omega
      simp only [dif_neg ha, dif_neg hb]
      apply he
      rw [Fin.le_def]
      simp only
      omega

  · intro a b hab
    simp only [Fin.mk.injEq] at hab
    exact e.symm.injective (Fin.ext (by omega))
  · intro j
    have hpos : ¬ (r - n + (e.symm j : ℕ)) < r - n := by omega
    simp only [dif_neg hpos]
    have hk : (⟨(r - n + (e.symm j : ℕ)) - (r - n), by omega⟩ : Fin n) = e.symm j :=
      Fin.ext (by simp)

    rw [hk, e.apply_symm_apply]
  · intro k hk
    by_cases hklt : (k : ℕ) < r - n
    · simp only [dif_pos hklt]
    · exfalso
      apply hk (e ⟨(k : ℕ) - (r - n), by omega⟩)
      apply Fin.ext
      simp only [Equiv.symm_apply_apply]
      omega
  · intro k hk
    refine ⟨e ⟨(k : ℕ) - (r - n), by omega⟩, ?_⟩
    apply Fin.ext
    simp only [Equiv.symm_apply_apply]
    omega


end Problems.LinearAlgebra.invariant_factor_decomposition
