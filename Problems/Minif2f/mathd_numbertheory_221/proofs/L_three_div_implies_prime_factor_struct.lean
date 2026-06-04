import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs

namespace Problems.Minif2f.mathd_numbertheory_221

-- entry_kind: Backward
theorem three_div_implies_prime_factor_struct :
    ∀ x : ℕ, x.divisors.card = 3 →
      ∃ p : ℕ, p.Prime ∧ x.primeFactors = {p} ∧ x.factorization p = 2 := by sorry

end Problems.Minif2f.mathd_numbertheory_221
