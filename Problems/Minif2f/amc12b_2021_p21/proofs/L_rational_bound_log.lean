import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- rational_bound_log: 4*log2 < 13/5*log3 via 2^20 < 3^13 and log_pow
theorem rational_bound_log :
    4 * Real.log 2 < (13:ℝ)/5 * Real.log 3 := by
  have h20 : Real.log ((2:ℝ)^20) = 20 * Real.log 2 := by
    rw [Real.log_pow]; push_cast; ring
  have h13 : Real.log ((3:ℝ)^13) = 13 * Real.log 3 := by
    rw [Real.log_pow]; push_cast; ring
  have hlt : Real.log ((2:ℝ)^20) < Real.log ((3:ℝ)^13) := by
    apply Real.log_lt_log
    · positivity
    · norm_num
  linarith

end Problems.Minif2f.amc12b_2021_p21
