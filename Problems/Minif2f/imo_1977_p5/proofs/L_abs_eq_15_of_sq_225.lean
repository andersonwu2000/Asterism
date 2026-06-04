import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs

namespace Problems.Minif2f.imo_1977_p5

-- abs_eq_15_of_sq_225: factors z²=225 as (z-15)(z+15)=0, then closes each branch by norm_num
theorem abs_eq_15_of_sq_225 : ∀ (z : ℤ), z ^ 2 = 225 → |z| = 15 := by
  intro z hz
  have hfact : (z - 15) * (z + 15) = 0 := by ring_nf; linarith
  rcases mul_eq_zero.mp hfact with h | h
  · have : z = 15 := by linarith
    subst this; norm_num
  · have : z = -15 := by linarith
    subst this; norm_num

end Problems.Minif2f.imo_1977_p5
