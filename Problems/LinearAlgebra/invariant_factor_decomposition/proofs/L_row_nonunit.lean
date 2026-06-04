import Mathlib
import Problems.LinearAlgebra.invariant_factor_decomposition.Defs

namespace Problems.LinearAlgebra.invariant_factor_decomposition

-- row_nonunit: a product of irreducible powers with at least one positive exponent is not a unit.
-- Extracts the positive-exponent factor via Finset.mul_prod_erase, applies
-- isUnit_of_mul_isUnit_left to conclude the factor would be a unit, then
-- isUnit_pow_iff + Irreducible.not_isUnit gives the contradiction.
-- entry_kind: Builder
theorem row_nonunit {K : Type*} [Field K] (s : ℕ) (q : Fin s → Polynomial K)
    (crow : Fin s → ℕ) (hirr : ∀ t, Irreducible (q t)) (h : ∃ t, 0 < crow t) :
    ¬ IsUnit (∏ t, q t ^ crow t) := by
  obtain ⟨t₀, ht₀⟩ := h
  intro hunit
  have hfact : ∏ t, q t ^ crow t = q t₀ ^ crow t₀ *
      ∏ t ∈ Finset.univ.erase t₀, q t ^ crow t :=
    (Finset.mul_prod_erase _ _ (Finset.mem_univ t₀)).symm
  rw [hfact] at hunit
  have hunit_factor : IsUnit (q t₀ ^ crow t₀) := isUnit_of_mul_isUnit_left hunit
  have hnotunit : ¬IsUnit (q t₀ ^ crow t₀) := by
    rw [isUnit_pow_iff (Nat.pos_iff_ne_zero.mp ht₀)]
    exact (hirr t₀).not_isUnit
  exact hnotunit hunit_factor

end Problems.LinearAlgebra.invariant_factor_decomposition