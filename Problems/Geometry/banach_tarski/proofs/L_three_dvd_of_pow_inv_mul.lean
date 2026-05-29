import Mathlib
import Problems.Geometry.banach_tarski.Defs

namespace Problems.Geometry.banach_tarski

-- entry_kind: Builder
-- three_dvd_of_pow_inv_mul: if (1/3)^n * q = 1 in ℝ with n ≥ 1, then 3 ∣ q (as q = 3^n)
theorem three_dvd_of_pow_inv_mul (n : ℕ) (q : ℤ) (hn : 0 < n)
    (h : (1 / 3 : ℝ) ^ n * (q : ℝ) = 1) : (3 : ℤ) ∣ q := by
  have hq : (q : ℝ) = (3 : ℝ) ^ n := by
    have key : (3 : ℝ) ^ n * ((1 / 3 : ℝ) ^ n * (q : ℝ)) = (3 : ℝ) ^ n := by
      rw [h]; ring
    rw [← mul_assoc, ← mul_pow] at key
    norm_num at key
    linarith
  have hq_int : q = (3 : ℤ) ^ n := by exact_mod_cast hq
  rw [hq_int]
  exact dvd_pow_self 3 (by omega)

end Problems.Geometry.banach_tarski
