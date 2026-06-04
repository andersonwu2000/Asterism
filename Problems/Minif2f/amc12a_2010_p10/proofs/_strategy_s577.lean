import Mathlib
import Problems.Minif2f.amc12a_2010_p10.Defs
import Problems.Minif2f.amc12a_2010_p10.proofs.L_closed_form

namespace Problems.Minif2f.amc12a_2010_p10

-- Reduce to closed form: a n = 4 * n + 1 for all n, then evaluate at n = 2010.
-- The closed form sub-goal abstracts the inductive content (solving for p, q from h₁-h₄
-- forces common difference 4; arithmetic recurrence h₀ propagates to all n). Once closed,
-- the parent's specific evaluation at n = 2010 is a pure norm_num check.
theorem s577 : ∀ (p q : ℝ) (a : ℕ → ℝ) (h₀ : ∀ n, a (n + 2) - a (n + 1) = a (n + 1) - a n)
    (h₁ : a 1 = p) (h₂ : a 2 = 9) (h₃ : a 3 = 3 * p - q) (h₄ : a 4 = 3 * p + q),
    a 2010 = 8041  := by
  intro p q a h₀ h₁ h₂ h₃ h₄
  have h_closed_form := closed_form p q a h₀ h₁ h₂ h₃ h₄ 2010
  norm_num at h_closed_form
  exact h_closed_form

end Problems.Minif2f.amc12a_2010_p10
