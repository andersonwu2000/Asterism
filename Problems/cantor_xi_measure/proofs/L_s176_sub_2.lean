import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s176_sub_2 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ x : ℝ, x ∈ ⋂ m : ℕ, cantorXi ξ m → ∀ m : ℕ, x ∈ cantorXi ξ m := by norm_num

end Problems.cantor_xi_measure
