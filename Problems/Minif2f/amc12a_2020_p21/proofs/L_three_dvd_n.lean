import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- three_dvd_n: 6 ∣ 5! ∣ lcm(5!,n) = 5·gcd(10!,n), coprimality 3⊥5 gives 3 ∣ gcd(10!,n) ∣ n
theorem three_dvd_n :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      (3:ℕ) ∣ n := by
  intro n ⟨h5, hlcm⟩
  have h6_left : (6 : ℕ) ∣ 5! := by norm_num [Nat.factorial]
  have h6_lcm : (6 : ℕ) ∣ Nat.lcm 5! n := h6_left.trans (Nat.dvd_lcm_left 5! n)
  rw [hlcm] at h6_lcm
  have h3_dvd_5gcd : (3 : ℕ) ∣ 5 * Nat.gcd 10! n := dvd_trans (by norm_num) h6_lcm
  have h3_dvd_gcd : (3 : ℕ) ∣ Nat.gcd 10! n := by
    have hcop : Nat.Coprime 3 5 := by norm_num
    exact hcop.dvd_of_dvd_mul_left h3_dvd_5gcd
  exact h3_dvd_gcd.trans (Nat.gcd_dvd_right 10! n)

end Problems.Minif2f.amc12a_2020_p21
