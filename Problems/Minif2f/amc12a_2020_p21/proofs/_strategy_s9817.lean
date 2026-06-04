import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_prime_pow_product_formula_2357

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: derive m ≠ 0 inline from m ∣ 5*10! ≠ 0, then invoke an abstract
-- factorization-product identity over the fixed prime support {2,3,5,7}.
-- Sub-goal `prime_pow_product_formula_2357` drops the lcm/gcd/divisibility
-- premises and only needs k ≠ 0 + support ⊆ {2,3,5,7} — strictly simpler.
theorem s9817 :
    ∀ m : ℕ, (5 ∣ m ∧ Nat.lcm 5! m = 5 * Nat.gcd 10! m) → m ∣ 5 * 10! →
      m.factorization.support ⊆ ({2, 3, 5, 7} : Finset ℕ) →
      m = 2^(m.factorization 2) * 3^(m.factorization 3)
          * 5^(m.factorization 5) * 7^(m.factorization 7)  := by
  intro m _ hdvd hsupp
  have hm : m ≠ 0 := fun h0 => by subst h0; norm_num at hdvd
  exact prime_pow_product_formula_2357 m hm hsupp


end Problems.Minif2f.amc12a_2020_p21
