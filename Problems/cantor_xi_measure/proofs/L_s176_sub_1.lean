import Mathlib
import Problems.cantor_xi_measure.Defs

namespace Problems.cantor_xi_measure

theorem s176_sub_1 : ∀ (ξ : ℝ), 0 < ξ → ξ < 1 →
    ∀ n : ℕ, ∀ x : ℝ, (∀ m : ℕ, x ∈ cantorXi ξ m) → x ∈ cantorXi ξ n := by simp_all

end Problems.cantor_xi_measure
