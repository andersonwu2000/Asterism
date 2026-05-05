import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s183_sub_1
import Problems.cantor_xi_measure.proofs.L_s183_sub_2
import Problems.cantor_xi_measure.proofs.L_s183_sub_3

namespace Problems.cantor_xi_measure

theorem s183 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ,
    Disjoint ((fun x => (1 - ξ) / 2 * x) '' cantorXi ξ n)
             ((fun x => (1 + ξ) / 2 + (1 - ξ) / 2 * x) '' cantorXi ξ n)  := by
  intro ξ hξ₁ hξ₂ n
  have h1 := s183_sub_1 ξ hξ₁ hξ₂ n
  have h2 := s183_sub_2 ξ hξ₁ hξ₂ n
  have h3 := s183_sub_3 ξ hξ₁ hξ₂
  exact Disjoint.mono h1 h2 h3

end Problems.cantor_xi_measure
