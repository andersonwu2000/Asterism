import Mathlib
import Problems.Minif2f.mathd_algebra_224.Defs

namespace Problems.Minif2f.mathd_algebra_224

-- mem_implies_sqrt_bound: fin_cases on the 8-element finset, then norm_num with sqrt_lt'/lt_sqrt
theorem mem_implies_sqrt_bound : ∀ n : ℕ,
    n ∈ ({5,6,7,8,9,10,11,12} : Finset ℕ) →
    (Real.sqrt (n : ℝ) < 7/2 ∧ 2 < Real.sqrt (n : ℝ)) := by
  intro n hn
  fin_cases hn <;> constructor <;> norm_num [Real.sqrt_lt', Real.lt_sqrt]

end Problems.Minif2f.mathd_algebra_224
