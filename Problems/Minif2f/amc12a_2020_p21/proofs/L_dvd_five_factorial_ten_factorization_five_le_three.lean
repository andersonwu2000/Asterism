import Mathlib
open Nat
namespace Problems.Minif2f.amc12a_2020_p21

-- dvd_five_factorial_ten_factorization_five_le_three: contrapose + ordProj_dvd closes the
-- 5-adic valuation bound for divisors of 5*10!; 5^4 ∤ 5*10! is decided by norm_num.
theorem dvd_five_factorial_ten_factorization_five_le_three :
    ∀ m : ℕ, m ∣ 5 * 10! → m.factorization 5 ≤ 3 := by
  intro m hm
  by_contra h
  push Not at h
  have hdvd : 5 ^ 4 ∣ m := (Nat.pow_dvd_pow 5 h).trans (ordProj_dvd m 5)
  have hcontra : 5 ^ 4 ∣ 5 * 10! := hdvd.trans hm
  norm_num [Nat.factorial] at hcontra

end Problems.Minif2f.amc12a_2020_p21
