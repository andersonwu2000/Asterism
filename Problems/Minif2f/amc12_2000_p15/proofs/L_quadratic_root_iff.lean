import Mathlib
import Problems.Minif2f.amc12_2000_p15.Defs

namespace Problems.Minif2f.amc12_2000_p15

-- quadratic_root_iff: factor 9y²+3y-6=0 as (3y-2)(y+1)=0 via linear_combination, then solve each root
theorem quadratic_root_iff : ∀ y : ℂ, 9 * y^2 + 3 * y + 1 = 7 ↔ y = 2/3 ∨ y = -1 := by
  intro y
  constructor
  · intro h
    have hfac : (3 * y - 2) * (y + 1) = 0 := by linear_combination (1 : ℂ) / 3 * h
    rcases mul_eq_zero.mp hfac with h1 | h2
    · left; linear_combination (1 : ℂ) / 3 * h1
    · right; linear_combination h2
  · rintro (rfl | rfl) <;> norm_num

end Problems.Minif2f.amc12_2000_p15
