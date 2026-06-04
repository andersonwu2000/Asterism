import Mathlib
import Problems.Minif2f.mathd_algebra_192.Defs

namespace Problems.Minif2f.mathd_algebra_192

-- Direct ℂ ring identity: substitute the three definitions, then close with
-- `linear_combination` over `Complex.I^2 = -1`.
theorem s648 : ∀ (q e d : ℂ) (h₀ : q = 11 - 5 * Complex.I) (h₁ : e = 11 + 5 * Complex.I) (h₂ : d = 2 * Complex.I), q * e * d = 292 * Complex.I  := by
  intro q e d h₀ h₁ h₂
  subst h₀ h₁ h₂
  have hI : Complex.I ^ 2 = -1 := Complex.I_sq
  linear_combination (-50 * Complex.I) * hI

end Problems.Minif2f.mathd_algebra_192
