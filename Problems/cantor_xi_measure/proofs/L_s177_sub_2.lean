import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s177_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (∀ n : ℕ, MeasureTheory.volume (cantorXi ξ n) = ENNReal.ofReal ((1 - ξ) ^ n)) →
    (∀ n : ℕ, cantorSet ξ ⊆ cantorXi ξ n) →
    (∀ (s t : Set ℝ), s ⊆ t → MeasureTheory.volume s ≤ MeasureTheory.volume t) →
    ∀ n : ℕ, MeasureTheory.volume (cantorSet ξ) ≤ MeasureTheory.volume (cantorXi ξ n) := by grind

end Problems.cantor_xi_measure
