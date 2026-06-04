import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs

namespace Problems.Minif2f.amc12a_2008_p15

-- two_pow_four_k_plus_four_mod_ten: 2^(4k+4) ≡ 6 (mod 10) by induction using pow_add + Nat.mul_mod
theorem two_pow_four_k_plus_four_mod_ten : ∀ (k : ℕ), 2^(4*k + 4) % 10 = 6 := by
  intro k
  induction k with
  | zero => norm_num
  | succ k ih =>
    have h : 4 * (k + 1) + 4 = (4 * k + 4) + 4 := by ring
    rw [h, pow_add, Nat.mul_mod, ih]
    norm_num

end Problems.Minif2f.amc12a_2008_p15
