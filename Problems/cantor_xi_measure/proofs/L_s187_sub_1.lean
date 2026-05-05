import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set MeasureTheory

/-- The right affine piece `x ↦ (1+ξ)/2 + (1-ξ)/2·x` agrees pointwise with
    `AffineMap.homothety 1 ((1-ξ)/2)`. Pure ring identity. -/
theorem s187_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ∀ n : ℕ, ∀ x : ℝ,
    (1 + ξ) / 2 + (1 - ξ) / 2 * x = AffineMap.homothety (1 : ℝ) ((1 - ξ) / 2) x := by
  intro ξ _ _ n x
  simp only [AffineMap.homothety_eq_lineMap, AffineMap.lineMap_apply_ring']
  ring

end Problems.cantor_xi_measure
