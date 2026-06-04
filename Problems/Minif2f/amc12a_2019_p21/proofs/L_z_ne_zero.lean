import Mathlib
import Problems.Minif2f.amc12a_2019_p21.Defs

namespace Problems.Minif2f.amc12a_2019_p21

-- z_ne_zero: (1 + I) / sqrt 2 is nonzero via div_ne_zero on numerator and coerced sqrt 2
theorem z_ne_zero : ∀ (z : ℂ) (h₀ : z = (1 + Complex.I) / Real.sqrt 2), z ≠ 0 := by
  intro z h₀
  subst h₀
  apply div_ne_zero
  · norm_num [Complex.ext_iff]
  · exact_mod_cast Real.sqrt_ne_zero'.mpr (by norm_num)

end Problems.Minif2f.amc12a_2019_p21
