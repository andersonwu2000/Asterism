import Mathlib
import Problems.Minif2f.mathd_algebra_10.Defs

namespace Problems.Minif2f.mathd_algebra_10

-- Pure rational arithmetic: 120/100*30 - 130/100*20 = 36 - 26 = 10, abs 10 = 10.
-- `norm_num` discharges the closed-form numeric equality and the `abs` evaluation.
theorem s504 : abs ((120 : ℝ) / 100 * 30 - 130 / 100 * 20) = 10  := by norm_num

end Problems.Minif2f.mathd_algebra_10
