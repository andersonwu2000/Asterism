import Mathlib
import Problems.Minif2f.mathd_algebra_116.Defs
import Problems.Minif2f.mathd_algebra_116.proofs.L_algebra_identity

namespace Problems.Minif2f.mathd_algebra_116

-- Substitute h₀ and reduce to a single algebraic identity: 2x² - 13x = -19/4
-- when x = (13 - √131)/4. Combine with h₁ via linarith to extract k = 19/4.
theorem s631 : ∀ (k x : ℝ) (h₀ : x = (13 - Real.sqrt 131) / 4) (h₁ : 2 * x ^ 2 - 13 * x + k = 0), k = 19 / 4  := by
  intro k x h₀ h₁
  have h_algebra := algebra_identity x h₀
  linarith

end Problems.Minif2f.mathd_algebra_116
