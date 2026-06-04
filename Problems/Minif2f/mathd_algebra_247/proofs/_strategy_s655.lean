import Mathlib
import Problems.Minif2f.mathd_algebra_247.Defs

namespace Problems.Minif2f.mathd_algebra_247

-- Direct: substitute n=3, then h₁ gives s=2 (via norm_num), then h₀ gives t=0 (linarith).
theorem s655 : ∀ (t s : ℝ) (n : ℤ) (h₀ : t = 2 * s - s ^ 2) (h₁ : s = n ^ 2 - 2 ^ n + 1) (_ : n = 3), t = 0  := by
  intro t s n h₀ h₁ hn
  subst hn
  norm_num at h₁
  subst h₁
  linarith

end Problems.Minif2f.mathd_algebra_247
