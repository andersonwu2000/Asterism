import Mathlib
import Problems.Minif2f.mathd_algebra_140.Defs
import Problems.Minif2f.mathd_algebra_140.proofs.L_ab_eq_twelve
import Problems.Minif2f.mathd_algebra_140.proofs.L_c_eq_seven

namespace Problems.Minif2f.mathd_algebra_140

-- Decompose by extracting two coefficient identities from the polynomial-equality hypothesis.
-- h_c : c = 7  (from h₁ 0, since -35 = -5*c)
-- h_ab : a * b = 12  (from comparing leading coefficients of h₁)
-- Combine: a*b - 3*c = 12 - 21 = -9 by linarith.
theorem s638 : ∀ (a b c : ℝ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c) (h₁ : ∀ x, 24 * x ^ 2 - 19 * x - 35 = (a * x - 5) * (2 * (b * x) + c)), a * b - 3 * c = -9  := by
  intro a b c h₀ h₁
  have h_c : c = 7 := c_eq_seven a b c h₀ h₁
  have h_ab : a * b = 12 := ab_eq_twelve a b c h₀ h₁
  linarith

end Problems.Minif2f.mathd_algebra_140
