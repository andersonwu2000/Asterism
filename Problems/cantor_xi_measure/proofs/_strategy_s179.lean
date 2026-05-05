import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s179_sub_1
import Problems.cantor_xi_measure.proofs.L_s179_sub_2

namespace Problems.cantor_xi_measure

theorem s179 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 → ENNReal.ofReal (1 - ξ) < 1  := by
  intro ξ hξ₁ hξ₂
  have h1 := s179_sub_1 ξ hξ₁ hξ₂
  exact s179_sub_2 ξ hξ₁ hξ₂ h1

end Problems.cantor_xi_measure
