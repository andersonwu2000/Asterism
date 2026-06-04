import Mathlib
import Problems.Minif2f.amc12a_2009_p25.proofs.L_base_25
import Problems.Minif2f.amc12a_2009_p25.proofs.L_base_26
import Problems.Minif2f.amc12a_2009_p25.proofs.L_periodic_from_bases

namespace Problems.Minif2f.amc12a_2009_p25

-- Decompose period-24 via two base cases plus an inductive closer.
-- Sub-goal `base_25` (Builder): a 25 = a 1 by unfolding the recurrence 23 times.
-- Sub-goal `base_26` (Builder): a 26 = a 2 by unfolding the recurrence 24 times.
-- Sub-goal `periodic_from_bases` (Backward): given a 25 = a 1 and a 26 = a 2,
--   two-step induction on n closes ∀ n ≥ 1, a (n+24) = a n using the recurrence.
theorem s9948 :
    ∀ (a : ℕ → ℝ) (h₀ : a 1 = 1) (h₁ : a 2 = 1 / Real.sqrt 3)
      (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1))),
      ∀ n, 1 ≤ n → a (n + 24) = a n  := by
  intro a h₀ h₁ h₂
  have h_25 := base_25 a h₀ h₁ h₂
  have h_26 := base_26 a h₀ h₁ h₂
  exact periodic_from_bases a h₀ h₁ h₂ h_25 h_26

end Problems.Minif2f.amc12a_2009_p25
