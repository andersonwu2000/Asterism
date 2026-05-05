import Mathlib

namespace Problems.cantor_xi_measure

theorem s179_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → (1 - ξ : ℝ) < 1 → ENNReal.ofReal (1 - ξ) < 1 := by norm_num

end Problems.cantor_xi_measure
