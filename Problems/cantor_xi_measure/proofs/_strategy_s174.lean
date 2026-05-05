import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s174_sub_1
import Problems.cantor_xi_measure.proofs.L_s174_sub_2

namespace Problems.cantor_xi_measure

theorem s174 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, cantorSet ξ ⊆ cantorXi ξ n  := by
  intro ξ hξ₁ hξ₂ n
  have h1 := s174_sub_1 ξ hξ₁ hξ₂
  have h2 := s174_sub_2 ξ hξ₁ hξ₂ n
  rw [h1]; exact h2

end Problems.cantor_xi_measure
