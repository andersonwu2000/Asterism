import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- n_dvd_five_mul_ten_factorial_2: chain n ∣ lcm 5! n = 5·gcd 10! n, and gcd 10! n ∣ 10!
-- Identical statement to n_dvd_five_mul_ten_factorial; proof is a direct reuse.
theorem n_dvd_five_mul_ten_factorial_2 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) → n ∣ 5 * 10! := by
  intro n ⟨_, hlcm⟩
  have h1 : n ∣ Nat.lcm 5! n := Nat.dvd_lcm_right _ _
  rw [hlcm] at h1
  exact h1.trans (Nat.mul_dvd_mul_left 5 (Nat.gcd_dvd_left 10! n))

end Problems.Minif2f.amc12a_2020_p21
