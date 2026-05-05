import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set MeasureTheory

/-- The scaling factor `(1-ξ)/2` is strictly positive when `0 < ξ < 1`. -/
theorem s187_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ∀ n : ℕ,
    0 < (1 - ξ) / 2 := by norm_num

end Problems.cantor_xi_measure
