import Mathlib
import Problems.Minif2f.amc12a_2009_p25.proofs.L_a_2009_eq_a_17
import Problems.Minif2f.amc12a_2009_p25.proofs.L_a_seventeen_eq_zero

namespace Problems.Minif2f.amc12a_2009_p25

-- Decomposition: combine periodicity (a 2009 = a 17) with a direct
-- computation showing a 17 = 0, then close via abs_zero.
theorem s9945 : ∀ (a : ℕ → ℝ) (h₀ : a 1 = 1) (h₁ : a 2 = 1 / Real.sqrt 3) (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1))), abs (a 2009) = 0  := by
  intro a h₀ h₁ h₂
  have h17 : a 17 = 0 := a_seventeen_eq_zero a h₀ h₁ h₂
  have hperiod : a 2009 = a 17 := a_2009_eq_a_17 a h₀ h₁ h₂
  rw [hperiod, h17, abs_zero]

end Problems.Minif2f.amc12a_2009_p25
