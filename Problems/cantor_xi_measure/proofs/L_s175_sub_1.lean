import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s175_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    cantorSet ξ ⊆ ⋂ n : ℕ, cantorXi ξ n := by
  intro ξ _ _
  unfold cantorSet
  exact Set.Subset.refl _

end Problems.cantor_xi_measure
