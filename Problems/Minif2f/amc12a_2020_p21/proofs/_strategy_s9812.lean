import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Direct proof: 2^3 = 8 ∣ 5! = 120, so 8 ∣ lcm(5!,n) = 5·gcd(10!,n); coprimality
-- 8 ⊥ 5 gives 8 ∣ gcd(10!,n) ∣ n (mirrors `three_dvd_n` recipe at prime 2^3).
theorem s9812 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      (2:ℕ)^3 ∣ n  := by
  intro n ⟨_, hlcm⟩
  have hp : (2:ℕ)^3 ∣ 5! := by norm_num [Nat.factorial]
  have hlcm_dvd : (2:ℕ)^3 ∣ Nat.lcm 5! n := hp.trans (Nat.dvd_lcm_left 5! n)
  rw [hlcm] at hlcm_dvd
  have hcop : Nat.Coprime ((2:ℕ)^3) 5 := by decide
  have h_gcd : (2:ℕ)^3 ∣ Nat.gcd 10! n := hcop.dvd_of_dvd_mul_left hlcm_dvd
  exact h_gcd.trans (Nat.gcd_dvd_right 10! n)

end Problems.Minif2f.amc12a_2020_p21
