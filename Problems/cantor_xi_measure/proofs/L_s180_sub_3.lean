import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s180_sub_3 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ENNReal.ofReal (1 - ξ) < 1 →
    Filter.Tendsto (fun n : ℕ => ENNReal.ofReal (1 - ξ) ^ n) Filter.atTop (nhds 0) := by norm_num

end Problems.cantor_xi_measure
