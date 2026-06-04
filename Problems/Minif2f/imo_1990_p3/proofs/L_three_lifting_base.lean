import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs

namespace Problems.Minif2f.imo_1990_p3

-- three_lifting_base: 3 ∣ 2^m + 1 for odd m, via (2 : ZMod 3) = -1 and Odd.neg_one_pow
theorem three_lifting_base :
    ∀ (m : ℕ), Odd m → ¬ (3 ∣ m) → 3 ^ (0 + 1) ∣ 2 ^ (3 ^ 0 * m) + 1 := by
  intro m hm _
  simp only [pow_zero, one_mul, Nat.pow_succ]
  have key : (2 : ZMod 3) ^ m + 1 = 0 := by
    have h2 : (2 : ZMod 3) = -1 := by decide
    rw [h2, Odd.neg_one_pow hm]; ring
  have cast_eq : ((2 ^ m + 1 : ℕ) : ZMod 3) = 0 := by push_cast; exact_mod_cast key
  rwa [CharP.cast_eq_zero_iff (ZMod 3) 3] at cast_eq

end Problems.Minif2f.imo_1990_p3
