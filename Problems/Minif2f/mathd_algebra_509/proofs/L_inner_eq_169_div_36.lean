import Mathlib
import Problems.Minif2f.mathd_algebra_509.Defs

namespace Problems.Minif2f.mathd_algebra_509

-- inner_eq_169_div_36: fold √80=4√5, √845=13√5, √45=3√5 then field_simp+nlinarith with √5·√5=5
theorem inner_eq_169_div_36 :
    (5 / Real.sqrt 80 + Real.sqrt 845 / 9 + Real.sqrt 45) / Real.sqrt 5 = (169 : ℝ) / 36 := by
  have h5ne : Real.sqrt 5 ≠ 0 := Real.sqrt_ne_zero'.mpr (by norm_num)
  have hsq : Real.sqrt 5 * Real.sqrt 5 = 5 := Real.mul_self_sqrt (by norm_num)
  have h80 : Real.sqrt 80 = 4 * Real.sqrt 5 := by
    rw [show (80 : ℝ) = 4^2 * 5 by norm_num, Real.sqrt_mul (by norm_num),
        Real.sqrt_sq (by norm_num)]
  have h845 : Real.sqrt 845 = 13 * Real.sqrt 5 := by
    rw [show (845 : ℝ) = 13^2 * 5 by norm_num, Real.sqrt_mul (by norm_num),
        Real.sqrt_sq (by norm_num)]
  have h45 : Real.sqrt 45 = 3 * Real.sqrt 5 := by
    rw [show (45 : ℝ) = 3^2 * 5 by norm_num, Real.sqrt_mul (by norm_num),
        Real.sqrt_sq (by norm_num)]
  rw [h80, h845, h45]
  field_simp
  nlinarith [hsq, sq_nonneg (Real.sqrt 5)]

end Problems.Minif2f.mathd_algebra_509
