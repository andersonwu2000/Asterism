import Mathlib
import Problems.Minif2f.amc12a_2009_p25.proofs.L_step_a13_a14
import Problems.Minif2f.amc12a_2009_p25.proofs.L_step_a17
import Problems.Minif2f.amc12a_2009_p25.proofs.L_step_a4_a5
import Problems.Minif2f.amc12a_2009_p25.proofs.L_step_a8_a9

namespace Problems.Minif2f.amc12a_2009_p25

-- Decomposition: cascade the 15-step computation into 4 chunks by
-- introducing intermediate milestone values (a4/a5, a8/a9, a13/a14)
-- so each sub-goal is a short 3-5 step algebraic computation.
-- Final chunk closes a 17 = 0 via the recurrence on a_15, a_16
-- (a_15 + a_16 = 0 makes the numerator vanish).
theorem s9946 :
    ∀ (a : ℕ → ℝ) (h₀ : a 1 = 1) (h₁ : a 2 = 1 / Real.sqrt 3)
      (h₂ : ∀ n, 1 ≤ n → a (n + 2) = (a n + a (n + 1)) / (1 - a n * a (n + 1))),
      a 17 = 0  := by
  intro a h₀ h₁ h₂
  have h45 := step_a4_a5 a h₀ h₁ h₂
  have h89 := step_a8_a9 a h₀ h₁ h₂ h45.1 h45.2
  have h1314 := step_a13_a14 a h₀ h₁ h₂ h89.1 h89.2
  exact step_a17 a h₀ h₁ h₂ h1314.1 h1314.2

end Problems.Minif2f.amc12a_2009_p25
