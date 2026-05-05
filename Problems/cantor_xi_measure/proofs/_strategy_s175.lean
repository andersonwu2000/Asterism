import Mathlib
import Problems.cantor_xi_measure.Defs
import Problems.cantor_xi_measure.proofs.L_s175_sub_1
import Problems.cantor_xi_measure.proofs.L_s175_sub_2

namespace Problems.cantor_xi_measure

theorem s175 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    cantorSet ξ = ⋂ n : ℕ, cantorXi ξ n  := by
  intro ξ hξ₁ hξ₂
  exact Set.Subset.antisymm (s175_sub_1 ξ hξ₁ hξ₂) (s175_sub_2 ξ hξ₁ hξ₂)

end Problems.cantor_xi_measure
