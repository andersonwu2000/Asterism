import Mathlib
import Problems.Minif2f.numbertheory_sqmod3in01d.Defs

namespace Problems.Minif2f.numbertheory_sqmod3in01d

-- sq_mod3_of_mod3_eq_two: introduce k with a = 3k+2, expand square via ring, omega closes
theorem sq_mod3_of_mod3_eq_two (a : ℤ) (h : a % 3 = 2) : a ^ 2 % 3 = 1 := by
  have key : a = 3 * (a / 3) + 2 := by
    have := Int.emod_add_mul_ediv a 3; omega
  obtain ⟨k, hk⟩ : ∃ k : ℤ, a = 3 * k + 2 := ⟨a / 3, key⟩
  have hq : a ^ 2 = 3 * (3 * k ^ 2 + 4 * k + 1) + 1 := by rw [hk]; ring
  obtain ⟨m, hm⟩ : ∃ m : ℤ, a ^ 2 = 3 * m + 1 := ⟨_, hq⟩
  omega

end Problems.Minif2f.numbertheory_sqmod3in01d
