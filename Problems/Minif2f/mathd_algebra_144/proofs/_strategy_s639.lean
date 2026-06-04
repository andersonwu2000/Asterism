import Mathlib
import Problems.Minif2f.mathd_algebra_144.Defs

namespace Problems.Minif2f.mathd_algebra_144

-- Direct closure by `omega`: substituting c = b + d and b = a + d into a+b+c=60
-- gives 3a+3d=60 hence a+d=20; the strict inequality a+b>c reduces to a>d,
-- so d<10. All steps are linear over ℕ/ℤ — omega discharges in one shot.
theorem s639 : ∀ (a b c d : ℕ) (h₀ : 0 < a ∧ 0 < b ∧ 0 < c ∧ 0 < d) (h₀ : (c : ℤ) - b = d) (h₁ : (b : ℤ) - a = d) (h₂ : a + b + c = 60) (h₃ : a + b > c), d < 10  := by
  intro a b c d hpos hcb hba habc hab
  omega

end Problems.Minif2f.mathd_algebra_144