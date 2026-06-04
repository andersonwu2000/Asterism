import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Direct leaf proof (sorry-free): apply the ordProj_dvd upper-bound recipe at p=3.
-- Chain n ∣ lcm 5! n = 5 * gcd 10! n ∣ 5*10!, then `¬ 3^5 ∣ 5*10!` (by norm_num on
-- 10!'s factorization at 3 = 4) combined with `Nat.pow_dvd_pow` + `ordProj_dvd n 3`
-- via contrapositive yields `n.factorization 3 < 5`, hence ≤ 4.
theorem s9799 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 3 ≤ 4  := by
  intro n ⟨h5, hlcm⟩
  have hndvd : n ∣ 5 * 10! := by
    have h1 : n ∣ Nat.lcm 5! n := Nat.dvd_lcm_right _ _
    rw [hlcm] at h1
    exact h1.trans (Nat.mul_dvd_mul_left 5 (Nat.gcd_dvd_left 10! n))
  have h35 : ¬ 3 ^ 5 ∣ 5 * 10! := by norm_num [Nat.factorial]
  suffices h : n.factorization 3 < 5 by omega
  by_contra hlt
  simp only [not_lt] at hlt
  exact h35 ((Nat.pow_dvd_pow 3 hlt).trans (ordProj_dvd n 3) |>.trans hndvd)

end Problems.Minif2f.amc12a_2020_p21
