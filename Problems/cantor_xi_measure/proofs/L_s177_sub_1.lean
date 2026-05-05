import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s177_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (∀ n : ℕ, MeasureTheory.volume (cantorXi ξ n) = ENNReal.ofReal ((1 - ξ) ^ n)) →
    (∀ n : ℕ, cantorSet ξ ⊆ cantorXi ξ n) →
    ∀ (s t : Set ℝ), s ⊆ t → MeasureTheory.volume s ≤ MeasureTheory.volume t := by
  intro _ξ _hξ₁ _hξ₂ _h1 _h2 s t h
  exact MeasureTheory.measure_mono h

end Problems.cantor_xi_measure
