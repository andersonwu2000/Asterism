import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_dvd_five_factorial_ten_factorization_five_le_three
import Problems.Minif2f.amc12a_2020_p21.proofs.L_dvd_five_mul_ten_factorial_factorization_five_le_three
import Problems.Minif2f.amc12a_2020_p21.proofs.L_n_dvd_five_mul_ten_factorial_2

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Pivot through divisibility: combine two strictly simpler lemmas.
-- (1) `n_dvd_five_mul_ten_factorial_2` — already proved sibling — turns
--     the lcm/gcd hypothesis into `n ∣ 5 * 10!`.
-- (2) `dvd_five_mul_ten_factorial_factorization_five_le_three` —
--     pure number-theoretic step, no parent hypothesis: any divisor of
--     `5 * 10! = 2^8·3^4·5^3·7` has its 5-adic valuation ≤ 3.
theorem s9796 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n.factorization 5 ≤ 3  := by
  intro n hn
  have h_dvd := n_dvd_five_mul_ten_factorial_2 n hn
  have h_bound := dvd_five_mul_ten_factorial_factorization_five_le_three
  exact h_bound n h_dvd

end Problems.Minif2f.amc12a_2020_p21
