import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs
import Problems.Minif2f.amc12a_2020_p21.proofs.L_factorization_prod_eq_2357

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- Decomposition: derive m ≠ 0 inline from m ∣ 5*10!, then invoke the generic
-- factorization-product identity over the fixed {2,3,5,7} support set.
-- Sub-goal `factorization_prod_eq_2357` is the abstract identity (no lcm/gcd
-- hypotheses); combinator is direct application.
theorem s9813 :
    ∀ m : ℕ, (5 ∣ m ∧ Nat.lcm 5! m = 5 * Nat.gcd 10! m) → m ∣ 5 * 10! →
      m.factorization.support ⊆ ({2, 3, 5, 7} : Finset ℕ) →
      m = 2^(m.factorization 2) * 3^(m.factorization 3)
          * 5^(m.factorization 5) * 7^(m.factorization 7)  := by
  intro m _ hdvd hsupp
  have hm : m ≠ 0 := fun h0 => by subst h0; norm_num at hdvd
  exact factorization_prod_eq_2357 m hm hsupp

end Problems.Minif2f.amc12a_2020_p21
