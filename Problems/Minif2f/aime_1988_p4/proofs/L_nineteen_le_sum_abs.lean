import Mathlib
import Problems.Minif2f.aime_1988_p4.Defs

namespace Problems.Minif2f.aime_1988_p4

-- entry_kind: Builder
theorem nineteen_le_sum_abs : ∀ (n : ℕ) (a : ℕ → ℝ) (h₀ : ∀ n, abs (a n) < 1) (h₁ : (∑ k ∈ Finset.range n, abs (a k)) = 19 + abs (∑ k ∈ Finset.range n, a k)), (19 : ℝ) ≤ (∑ k ∈ Finset.range n, abs (a k)) := by simp_all only [le_add_iff_nonneg_right, abs_nonneg, implies_true]

end Problems.Minif2f.aime_1988_p4
