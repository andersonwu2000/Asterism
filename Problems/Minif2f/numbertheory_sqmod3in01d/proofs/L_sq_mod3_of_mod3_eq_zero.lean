import Mathlib
import Problems.Minif2f.numbertheory_sqmod3in01d.Defs

namespace Problems.Minif2f.numbertheory_sqmod3in01d

-- sq_mod3_of_mod3_eq_zero: extract divisor k via Int.dvd_of_emod_eq_zero, substitute,
-- then ring_nf reduces (3*k)^2 to a linear multiple of 3 that omega closes.
theorem sq_mod3_of_mod3_eq_zero (a : ℤ) (h : a % 3 = 0) : a ^ 2 % 3 = 0 := by
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero h
  subst hk
  ring_nf
  omega

end Problems.Minif2f.numbertheory_sqmod3in01d
