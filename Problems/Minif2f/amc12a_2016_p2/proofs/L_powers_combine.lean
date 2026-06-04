import Mathlib
import Problems.Minif2f.amc12a_2016_p2.Defs

namespace Problems.Minif2f.amc12a_2016_p2

-- powers_combine: rewrites 100 = 10^2 then uses rpow_mul and rpow_add to collapse to 10^(5x)
theorem powers_combine : ∀ (x : ℝ), (10 : ℝ)^x * (100 : ℝ)^(2*x) = (10 : ℝ)^(5*x) := by
  intro x
  have h100 : (100 : ℝ) = (10 : ℝ)^(2 : ℝ) := by norm_num
  rw [h100, ← Real.rpow_mul (by norm_num : (0 : ℝ) ≤ 10)]
  rw [← Real.rpow_add (by norm_num : (0 : ℝ) < 10)]
  congr 1
  ring

end Problems.Minif2f.amc12a_2016_p2
