import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Direct upper-bound recipe at p = 2 (parallels seven_factorization_le_one):
-- chain n ∣ Nat.lcm 5! n = 5·gcd 10! n ∣ 5·10!, then since ¬ 2^9 ∣ 5·10!
-- (norm_num on Nat.factorial), `ordProj_dvd n 2` + `Nat.pow_dvd_pow` force
-- `n.factorization 2 < 9`. No sub-goals — leaf-bypass ships this directly.
theorem s9801 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 2 ≤ 8  := by
  intro n ⟨h5, hlcm⟩
  have hn : n ≠ 0 := by
    intro hn; subst hn; simp at hlcm; exact absurd hlcm (Nat.factorial_pos 10).ne'
  have hndvd : n ∣ 5 * 10 ! := by
    have h1 : n ∣ Nat.lcm 5 ! n := Nat.dvd_lcm_right 5 ! n
    rw [hlcm] at h1
    exact h1.trans (Nat.mul_dvd_mul_left 5 (Nat.gcd_dvd_left 10 ! n))
  have h29 : ¬ 2 ^ 9 ∣ 5 * 10 ! := by norm_num [Nat.factorial]
  suffices h : n.factorization 2 < 9 by omega
  by_contra hlt
  simp only [not_lt] at hlt
  exact h29 ((Nat.pow_dvd_pow 2 hlt).trans (ordProj_dvd n 2) |>.trans hndvd)

end Problems.Minif2f.amc12a_2020_p21
