import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s186_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ((1 - ξ) / 2 : ℝ) ^ Module.finrank ℝ ℝ = (1 - ξ) / 2 := by norm_num

end Problems.cantor_xi_measure
