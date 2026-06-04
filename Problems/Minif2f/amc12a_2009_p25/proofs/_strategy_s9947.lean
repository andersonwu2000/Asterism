import Mathlib
import Problems.Minif2f.amc12a_2009_p25.proofs.L_periodicity_24
import Problems.Minif2f.amc12a_2009_p25.proofs.L_period_iter

namespace Problems.Minif2f.amc12a_2009_p25

-- Decompose `a 2009 = a 17` via period-24 of the recurrence.
-- Sub-goal 1 (periodicity_24): the sequence has period 24 for n ≥ 1.
-- Sub-goal 2 (period_iter): iterating period-24 k times keeps a(17 + 24k) = a 17.
-- Closer: instantiate k = 83 and use 2009 = 17 + 24*83.
theorem s9947 :
    ∀ (a : ℕ → ℝ) (h₀ : a 1 = 1) (h₁ : a 2 = 1 / Real.sqrt 3)
      (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1))),
      a 2009 = a 17  := by
  intro a h₀ h₁ h₂
  have h_period : ∀ n, 1 ≤ n → a (n + 24) = a n := periodicity_24 a h₀ h₁ h₂
  have h_iter : ∀ k, a (17 + 24 * k) = a 17 := period_iter a h₀ h₁ h₂ h_period
  have h_eq : (2009 : ℕ) = 17 + 24 * 83 := by norm_num
  rw [h_eq]
  exact h_iter 83

end Problems.Minif2f.amc12a_2009_p25
