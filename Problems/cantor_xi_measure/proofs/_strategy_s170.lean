import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s170_sub_1
import Problems.cantor_xi_measure.proofs.L_s170_sub_2
import Problems.cantor_xi_measure.proofs.L_s170_sub_3
import Problems.cantor_xi_measure.proofs.L_s170_sub_4

namespace Problems.cantor_xi_measure

theorem s170 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    MeasureTheory.volume (cantorSet ξ) = 0  := by
  intro ξ hξ₁ hξ₂
  have h1 := s170_sub_1 ξ hξ₁ hξ₂
  have h2 := s170_sub_2 ξ hξ₁ hξ₂
  exact s170_sub_4 ξ hξ₁ hξ₂ (s170_sub_3 ξ hξ₁ hξ₂ h1 h2)

end Problems.cantor_xi_measure
