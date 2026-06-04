import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_nonzero_n
import Problems.Minif2f.amc12a_2020_p21.proofs.L_three_dvd_n

open Nat

namespace Problems.Minif2f.amc12a_2020_p21
-- Lower bound 1 ≤ n.factorization 3 via prime-divides-iff-one-le-factorization recipe.
-- Sub-goals: (1) 3 ∣ n (the divisibility content) and (2) n ≠ 0 (factorization is
-- well-defined). Combined with `(Nat.Prime.pow_dvd_iff_le_factorization _ _).mp`
-- applied to the canonical `3 ∣ n` form (defeq to `3 ^ 1 ∣ n`).
theorem s9798 :
    ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      1 ≤ n.factorization 3  := by
  intro n hyp
  have h_dvd := three_dvd_n n hyp
  have h_ne := nonzero_n n hyp
  exact (Nat.Prime.pow_dvd_iff_le_factorization Nat.prime_three h_ne).mp h_dvd

end Problems.Minif2f.amc12a_2020_p21
