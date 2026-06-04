import Mathlib

namespace Problems.Minif2f.amc12a_2009_p25

-- entry_kind: Builder
theorem induction_step
    (a : ℕ → ℝ)
    (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1)))
    (n : ℕ) (hn : 1 ≤ n)
    (ih1 : a (n + 24) = a n)
    (ih2 : a (n + 1 + 24) = a (n + 1)) :
    a (n + 2 + 24) = a (n + 2) := by simp_all only [le_add_iff_nonneg_left, zero_le]

end Problems.Minif2f.amc12a_2009_p25
