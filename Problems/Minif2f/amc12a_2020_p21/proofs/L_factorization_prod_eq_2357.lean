import Mathlib
import Problems.Minif2f.amc12a_2020_p21.Defs

open Nat

namespace Problems.Minif2f.amc12a_2020_p21

-- entry_kind: Builder
theorem factorization_prod_eq_2357 :
    ∀ k : ℕ, k ≠ 0 → k.factorization.support ⊆ ({2, 3, 5, 7} : Finset ℕ) →
      k = 2^(k.factorization 2) * 3^(k.factorization 3)
          * 5^(k.factorization 5) * 7^(k.factorization 7) := by sorry

end Problems.Minif2f.amc12a_2020_p21
