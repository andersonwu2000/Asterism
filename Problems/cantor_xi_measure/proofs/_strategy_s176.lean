import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s176_sub_1
import Problems.cantor_xi_measure.proofs.L_s176_sub_2

namespace Problems.cantor_xi_measure

theorem s176 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, (⋂ m : ℕ, cantorXi ξ m) ⊆ cantorXi ξ n  := by
  intro ξ hξ₁ hξ₂ n
  intro x hx
  have hmem := s176_sub_2 ξ hξ₁ hξ₂ x hx
  exact s176_sub_1 ξ hξ₁ hξ₂ n x hmem

end Problems.cantor_xi_measure
