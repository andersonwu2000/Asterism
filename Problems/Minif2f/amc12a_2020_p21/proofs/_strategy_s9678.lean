import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_witness
import Problems.Minif2f.amc12a_2020_p21.proofs.L_image_from_witness

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: split predicate→image into (1) factorization-witness extraction
-- (the hard arithmetic step that the lcm/gcd identity + 5∣n forces the prime
-- exponents into the given ranges) and (2) a purely structural membership
-- construction from the witness via `Finset.mem_image` + `Finset.mem_product`.
theorem s9678 : ∀ n : ℕ, (5 ∣ n ∧ Nat.lcm 5! n = 5 * Nat.gcd 10! n) →
      n ∈ ((Finset.Icc 3 8 ×ˢ Finset.Icc 1 4 ×ˢ Finset.Icc 0 1).image
      (fun p : ℕ × ℕ × ℕ => 2^p.1 * 3^p.2.1 * 5^3 * 7^p.2.2))  := by
  intro n hpred
  have h_factorization_witness := factorization_witness n hpred
  exact image_from_witness n h_factorization_witness

end Problems.Minif2f.amc12a_2020_p21
