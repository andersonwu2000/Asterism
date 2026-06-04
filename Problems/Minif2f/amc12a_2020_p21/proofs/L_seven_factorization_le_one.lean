import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- seven_factorization_le_one: n ∣ 5*10! via lcm/gcd chain; since 7^2 ∤ 5*10!, ordProj gives bound.
theorem seven_factorization_le_one :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 7 ≤ 1 := by
  intro n ⟨h5, hlcm⟩
  have hn : n ≠ 0 := by
    intro hn; subst hn; simp at hlcm; exact absurd hlcm (Nat.factorial_pos 10).ne'
  have hndvd : n ∣ 5 * 10 ! := by
    have h1 : n ∣ Nat.lcm 5 ! n := Nat.dvd_lcm_right 5 ! n
    rw [hlcm] at h1
    exact h1.trans (Nat.mul_dvd_mul_left 5 (Nat.gcd_dvd_left 10 ! n))
  have h72 : ¬ 7 ^ 2 ∣ 5 * 10 ! := by norm_num [Nat.factorial]
  suffices h : n.factorization 7 < 2 by omega
  by_contra hlt
  simp only [not_lt] at hlt
  exact h72 ((Nat.pow_dvd_pow 7 hlt).trans (ordProj_dvd n 7) |>.trans hndvd)

end Problems.Minif2f.amc12a_2020_p21
