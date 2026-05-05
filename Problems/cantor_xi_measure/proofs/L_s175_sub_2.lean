import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s175_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    (⋂ n : ℕ, cantorXi ξ n) ⊆ cantorSet ξ := by aesop

end Problems.cantor_xi_measure
