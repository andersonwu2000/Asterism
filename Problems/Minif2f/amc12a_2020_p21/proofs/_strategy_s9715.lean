import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_canonical_factorization_form
import Problems.Minif2f.amc12a_2020_p21.proofs.L_prime_exponent_bounds

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: pick the canonical witness `(a,b,d) = (n.factorization 2,
-- n.factorization 3, n.factorization 7)` and split into (1) prime-exponent
-- bounds at 2/3/7 derived from the lcm/gcd identity, and (2) the canonical
-- product form (no other primes + exponent at 5 is forced to 3).
theorem s9715 : ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
    ∃ a b d : ℕ,
      (a ∈ Finset.Icc 3 8 ∧ b ∈ Finset.Icc 1 4 ∧ d ∈ Finset.Icc 0 1) ∧
      n = 2^a * 3^b * 5^3 * 7^d  := by
  intro n h
  have h_bounds := prime_exponent_bounds n h
  have h_form := canonical_factorization_form n h
  exact ⟨n.factorization 2, n.factorization 3, n.factorization 7,
         h_bounds, h_form⟩

end Problems.Minif2f.amc12a_2020_p21
