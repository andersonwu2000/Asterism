import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set

theorem s182_sub_3 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ (S : Set ℝ), IsCompact S → IsCompact ((fun x : ℝ => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' S) := by
  intro ξ _hξ₁ _hξ₂ S hS
  exact hS.image (by fun_prop)

end Problems.cantor_xi_measure
