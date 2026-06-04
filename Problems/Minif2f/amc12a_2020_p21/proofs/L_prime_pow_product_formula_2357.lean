import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- prime_pow_product_formula_2357: expand k via Finsupp.prod_of_support_subset over {2,3,5,7}
-- using Nat.prod_factorization_pow_eq_self, then ring closes the associativity gap
theorem prime_pow_product_formula_2357 :
    ∀ k : ℕ, k ≠ 0 → k.factorization.support ⊆ ({2, 3, 5, 7} : Finset ℕ) →
      k = 2^(k.factorization 2) * 3^(k.factorization 3)
          * 5^(k.factorization 5) * 7^(k.factorization 7) := by
  intro k hk hsup
  conv_lhs =>
    rw [← Nat.prod_factorization_pow_eq_self hk]
    rw [Finsupp.prod_of_support_subset _ hsup _ (fun a _ => pow_zero a)]
    simp only [Finset.prod_insert (show (2:ℕ) ∉ ({3,5,7} : Finset ℕ) by decide),
               Finset.prod_insert (show (3:ℕ) ∉ ({5,7} : Finset ℕ) by decide),
               Finset.prod_insert (show (5:ℕ) ∉ ({7} : Finset ℕ) by decide),
               Finset.prod_singleton]
  ring

end Problems.Minif2f.amc12a_2020_p21
