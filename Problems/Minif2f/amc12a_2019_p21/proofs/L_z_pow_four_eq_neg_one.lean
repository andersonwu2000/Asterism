import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs

namespace Problems.Minif2f.amc12a_2019_p21

-- z_pow_four_eq_neg_one: show z=(1+i)/√2 satisfies z^4=-1 via intermediate z^2=i
-- Establishes z^2 = i by field_simp + sqrt^2=2 + I^2=-1, then squares to get I^2=-1.
theorem z_pow_four_eq_neg_one : ∀ (z : ℂ) (h₀ : z = (1 + Complex.I) / Real.sqrt 2), z ^ 4 = -1 := by
  intro z h₀
  subst h₀
  have hsqrt : (Real.sqrt 2 : ℝ) ≠ 0 := Real.sqrt_ne_zero'.mpr (by norm_num)
  have hsqrtC : (Real.sqrt 2 : ℂ) ≠ 0 := by exact_mod_cast hsqrt
  have hsq : (Real.sqrt 2 : ℝ) ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have hz2 : ((1 + Complex.I) / ↑(Real.sqrt 2)) ^ 2 = Complex.I := by
    field_simp
    have hsqC : (↑(Real.sqrt 2) : ℂ) ^ 2 = 2 := by exact_mod_cast hsq
    rw [hsqC]
    ring_nf
    rw [Complex.I_sq]
    ring
  calc ((1 + Complex.I) / ↑(Real.sqrt 2)) ^ 4
      = (((1 + Complex.I) / ↑(Real.sqrt 2)) ^ 2) ^ 2 := by ring
    _ = Complex.I ^ 2 := by rw [hz2]
    _ = -1 := Complex.I_sq

end Problems.Minif2f.amc12a_2019_p21
