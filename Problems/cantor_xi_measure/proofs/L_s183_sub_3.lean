import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

open Set

/-- The intervals [0, (1-ξ)/2] and [(1+ξ)/2, 1] are disjoint when ξ > 0. -/
theorem s183_sub_3 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    Disjoint (Set.Icc 0 ((1 - ξ) / 2) : Set ℝ) (Set.Icc ((1 + ξ) / 2) 1) := by grind

end Problems.cantor_xi_measure
