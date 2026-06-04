import Mathlib
import Problems.Minif2f.aime_1990_p2.Defs

namespace Problems.Minif2f.aime_1990_p2

-- sum_pow32_eq_cube: rewrite 52+6√43=(3+√43)² then use rpow_mul to collapse (·²)^(3/2)=(·)^3
theorem sum_pow32_eq_cube : (52 + 6 * Real.sqrt 43) ^ ((3 : ℝ) / 2) = (3 + Real.sqrt 43) ^ 3 := by
  have h43 : (0 : ℝ) ≤ 43 := by norm_num
  have h43_sqrt : Real.sqrt 43 ^ 2 = 43 := Real.sq_sqrt h43
  have h3sqrt43_nonneg : (0 : ℝ) ≤ 3 + Real.sqrt 43 := by
    have := Real.sqrt_nonneg 43
    linarith
  have h_sq : (52 + 6 * Real.sqrt 43 : ℝ) = (3 + Real.sqrt 43) ^ 2 := by
    nlinarith [h43_sqrt]
  rw [h_sq, ← Real.rpow_natCast (3 + Real.sqrt 43) 2, ← Real.rpow_mul h3sqrt43_nonneg,
      ← Real.rpow_natCast (3 + Real.sqrt 43) 3]
  norm_num

end Problems.Minif2f.aime_1990_p2
