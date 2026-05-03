import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem main : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    MeasureTheory.volume (cantorSet ξ) = 0 := by sorry

end Problems.cantor_xi_measure
