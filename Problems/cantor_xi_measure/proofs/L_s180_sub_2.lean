import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s180_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ∀ n : ℕ,
    ENNReal.ofReal ((1 - ξ) ^ n) = ENNReal.ofReal (1 - ξ) ^ n := by
  intro ξ _hξ₁ hξ₂ n
  exact ENNReal.ofReal_pow (by linarith) n

end Problems.cantor_xi_measure
