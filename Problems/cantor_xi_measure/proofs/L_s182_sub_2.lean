import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set

theorem s182_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ (S : Set ℝ), IsCompact S → IsCompact ((fun x : ℝ => (1 - ξ) / 2 * x) '' S) := by
  intro ξ _hξ₁ _hξ₂ S hS
  exact hS.image (continuous_const_mul _)

end Problems.cantor_xi_measure
