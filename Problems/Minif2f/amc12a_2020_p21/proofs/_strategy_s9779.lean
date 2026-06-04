import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_form_of_dvd_5_mul_10_fact
import Problems.Minif2f.amc12a_2020_p21.proofs.L_n_dvd_five_mul_ten_factorial

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: split into (1) extracting `n ∣ 5 * 10!` from the
-- lcm/gcd hypothesis (chain `n ∣ lcm 5! n = 5·gcd 10! n ∣ 5·10!`), and
-- (2) deducing the canonical 2/3/5/7 product form from `n ∣ 5·10!`
-- (since `5·10! = 2^8·3^4·5^3·7`, its divisors have factorization
-- support ⊆ {2,3,5,7}).  Combinator chains the two via the new premise.
theorem s9779 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n = 2^(n.factorization 2) * 3^(n.factorization 3)
          * 5^(n.factorization 5) * 7^(n.factorization 7)  := by
  intro n h
  have h_dvd := n_dvd_five_mul_ten_factorial n h
  have h_form := factorization_form_of_dvd_5_mul_10_fact
  exact h_form n h h_dvd

end Problems.Minif2f.amc12a_2020_p21
