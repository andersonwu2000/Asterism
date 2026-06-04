import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_five_eq_three
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_support_2357

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: split the canonical form into (1) support confined to
-- {2,3,5,7}, giving `n = 2^a · 3^b · 5^(n.fact 5) · 7^d`, and
-- (2) the exponent at 5 is exactly 3; rewrite (2) into (1) to close.
theorem s9759 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n = 2^(n.factorization 2) * 3^(n.factorization 3) * 5^3 *
          7^(n.factorization 7)  := by
  intro n h
  have h_support := factorization_support_2357 n h
  have h_five := factorization_five_eq_three n h
  rw [h_five] at h_support
  exact h_support


end Problems.Minif2f.amc12a_2020_p21

