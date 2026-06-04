import Mathlib
import Problems.Minif2f.amc12b_2003_p6.Defs

namespace Problems.Minif2f.amc12b_2003_p6

-- entry_kind: Builder
theorem u_zero_eq_a : ∀ (a r : ℝ) (u : ℕ → ℝ) (h₀ : ∀ k, u k = a * r ^ k)
    (h₁ : u 1 = 2) (h₂ : u 3 = 6), u 0 = a := by simp_all only [pow_one, pow_zero, mul_one, implies_true]

end Problems.Minif2f.amc12b_2003_p6
