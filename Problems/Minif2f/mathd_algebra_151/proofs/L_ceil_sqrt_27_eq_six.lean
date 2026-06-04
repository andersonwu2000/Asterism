import Mathlib
import Problems.Minif2f.mathd_algebra_151.Defs

namespace Problems.Minif2f.mathd_algebra_151

-- ceil_sqrt_27_eq_six: bound sqrt 27 between 5 and 6 via sq_sqrt + nlinarith, then use
-- Int.lt_ceil / Int.ceil_le to pin the integer ceiling to 6.
theorem ceil_sqrt_27_eq_six : Int.ceil (Real.sqrt 27) = 6 := by
  have hsq : Real.sqrt 27 ^ 2 = 27 := Real.sq_sqrt (by norm_num)
  have hnn : 0 ≤ Real.sqrt 27 := Real.sqrt_nonneg 27
  have h1 : (5 : ℝ) < Real.sqrt 27 := by nlinarith
  have h2 : Real.sqrt 27 ≤ (6 : ℝ) := by nlinarith
  have h3 : (5 : ℤ) < Int.ceil (Real.sqrt 27) := Int.lt_ceil.mpr (by exact_mod_cast h1)
  have h4 : Int.ceil (Real.sqrt 27) ≤ (6 : ℤ) := Int.ceil_le.mpr (by exact_mod_cast h2)
  omega

end Problems.Minif2f.mathd_algebra_151
