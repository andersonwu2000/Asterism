import Mathlib
import Problems.Minif2f.aime_1990_p2.Defs

namespace Problems.Minif2f.aime_1990_p2

-- diff_pow32_eq_cube: (52-6√43)^(3/2) = (√43-3)^3 via sq identity + rpow_mul
theorem diff_pow32_eq_cube : (52 - 6 * Real.sqrt 43) ^ ((3 : ℝ) / 2) = (Real.sqrt 43 - 3) ^ 3 := by
  have h43 : Real.sqrt 43 ^ 2 = 43 := Real.sq_sqrt (by norm_num)
  have hsq : (52 : ℝ) - 6 * Real.sqrt 43 = (Real.sqrt 43 - 3) ^ 2 := by nlinarith
  have hnn : (0 : ℝ) ≤ Real.sqrt 43 - 3 := by
    have h9 : Real.sqrt 9 = 3 := by
      rw [show (9 : ℝ) = 3 ^ 2 by norm_num]
      exact Real.sqrt_sq (by norm_num)
    have h : Real.sqrt 9 ≤ Real.sqrt 43 := Real.sqrt_le_sqrt (by norm_num)
    linarith [h9 ▸ h]
  rw [hsq, ← Real.rpow_natCast (Real.sqrt 43 - 3) 2, ← Real.rpow_mul hnn,
      show (↑(2 : ℕ) : ℝ) * (3 / 2) = ↑(3 : ℕ) from by norm_num, Real.rpow_natCast]

end Problems.Minif2f.aime_1990_p2
