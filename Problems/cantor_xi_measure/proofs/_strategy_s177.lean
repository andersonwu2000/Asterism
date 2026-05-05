import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s177_sub_1
import Problems.cantor_xi_measure.proofs.L_s177_sub_2

namespace Problems.cantor_xi_measure

theorem s177 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (∀ n : ℕ, MeasureTheory.volume (cantorXi ξ n) = ENNReal.ofReal ((1 - ξ) ^ n)) →
    (∀ n : ℕ, cantorSet ξ ⊆ cantorXi ξ n) →
    ∀ n : ℕ, MeasureTheory.volume (cantorSet ξ) ≤ MeasureTheory.volume (cantorXi ξ n)  := by
  intro ξ hξ₁ hξ₂ h1 h2
  have hmono := s177_sub_1 ξ hξ₁ hξ₂ h1 h2
  exact s177_sub_2 ξ hξ₁ hξ₂ h1 h2 hmono

end Problems.cantor_xi_measure
