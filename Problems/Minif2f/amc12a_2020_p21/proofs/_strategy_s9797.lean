import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_canonical_form_from_support_2357
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_support_subset_2357

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Split into (A) support claim from divisibility and (B) generic product formula.
-- A: m ∣ 5*10! = 2^8·3^4·5^3·7 forces m.factorization.support ⊆ {2,3,5,7}.
-- B: For support ⊆ {2,3,5,7}, the generic factorization-product identity
--    (with m ≠ 0 derived internally from m ∣ 5*10!) gives the formula.
theorem s9797 :
    ∀ m : ℕ, (5 ∣ m ∧ Nat.lcm 5! m = 5 * Nat.gcd 10! m) → m ∣ 5 * 10! →
      m = 2^(m.factorization 2) * 3^(m.factorization 3)
          * 5^(m.factorization 5) * 7^(m.factorization 7)  := by
  intro m h hdvd
  have h_supp : m.factorization.support ⊆ ({2, 3, 5, 7} : Finset ℕ) :=
    factorization_support_subset_2357 m h hdvd
  exact canonical_form_from_support_2357 m h hdvd h_supp






end Problems.Minif2f.amc12a_2020_p21

