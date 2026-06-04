import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs

namespace Problems.Minif2f.mathd_numbertheory_221

-- entry_kind: Builder
theorem factorization_eq_single_of_struct :
    ∀ x p : ℕ, x.primeFactors = {p} → x.factorization p = 2 →
      x.factorization = Finsupp.single p 2 := by sorry

end Problems.Minif2f.mathd_numbertheory_221
