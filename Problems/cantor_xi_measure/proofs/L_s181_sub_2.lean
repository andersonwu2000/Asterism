import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s181_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (∀ n : ℕ, MeasureTheory.volume (cantorSet ξ) ≤ ENNReal.ofReal ((1 - ξ) ^ n)) →
    Filter.Tendsto (fun n : ℕ => ENNReal.ofReal ((1 - ξ) ^ n)) Filter.atTop (nhds 0) →
    MeasureTheory.volume (cantorSet ξ) ≤ 0 →
    MeasureTheory.volume (cantorSet ξ) = 0 := by norm_num

end Problems.cantor_xi_measure
