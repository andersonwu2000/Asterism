import Mathlib
import Problems.Minif2f.amc12_2001_p9.Defs

namespace Problems.Minif2f.amc12_2001_p9

-- Direct proof: apply h₀ at x=500, y=6/5 (both positive); use 500*(6/5)=600 and h₁.
-- f(600) = f(500*(6/5)) = f(500)/(6/5) = 3/(6/5) = 5/2.
theorem s566 : ∀ (f : ℝ → ℝ) (h₀ : ∀ x > 0, ∀ y > 0, f (x * y) = f x / y)
    (h₁ : f 500 = 3), f 600 = 5 / 2 := by
  intro f h₀ h₁
  have h500 : (500 : ℝ) > 0 := by norm_num
  have h65 : (6 / 5 : ℝ) > 0 := by norm_num
  have h2 : f ((500 : ℝ) * (6 / 5)) = f 500 / (6 / 5) :=
    h₀ 500 h500 (6 / 5) h65
  have heq : (500 : ℝ) * (6 / 5) = 600 := by norm_num
  rw [heq, h₁] at h2
  rw [h2]
  norm_num

end Problems.Minif2f.amc12_2001_p9
