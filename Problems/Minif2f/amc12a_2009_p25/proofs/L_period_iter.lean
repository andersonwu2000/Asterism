import Mathlib

namespace Problems.Minif2f.amc12a_2009_p25

-- period_iter: induction on k, each step applies h_period to shift index by 24
theorem period_iter (a : ℕ → ℝ) (h₀ : a 1 = 1) (h₁ : a 2 = 1 / Real.sqrt 3)
    (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1)))
    (h_period : ∀ n, 1 ≤ n → a (n + 24) = a n)
    (k : ℕ) : a (17 + 24 * k) = a 17 := by
  induction k with
  | zero => simp
  | succ k ih =>
    have hstep : a (17 + 24 * (k + 1)) = a (17 + 24 * k) := by
      have heq : 17 + 24 * (k + 1) = (17 + 24 * k) + 24 := by ring
      rw [heq]
      exact h_period (17 + 24 * k) (by omega)
    rw [hstep, ih]

end Problems.Minif2f.amc12a_2009_p25
