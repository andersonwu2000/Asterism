import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_prod_three_implies_struct

namespace Problems.Minif2f.mathd_numbertheory_221

-- Decompose `divisors.card = 3 → ∃ p prime, primeFactors = {p} ∧ factorization p = 2`
-- into (a) rewriting via `Nat.card_divisors` to the prime-factorization product form
-- (b) the combinatorial sub-goal `prod_three_implies_struct`: a product of `(k_i + 1)`
-- over primeFactors equaling 3 forces a singleton support with multiplicity 2.
-- The sub-goal drops `divisors.card`, replaces it with the algebraic product hypothesis,
-- and becomes a pure factorization-support argument independent of the divisor count.
theorem s9705 :
    ∀ x : ℕ, x.divisors.card = 3 →
      ∃ p : ℕ, p.Prime ∧ x.primeFactors = {p} ∧ x.factorization p = 2  := by
  intro x hcard
  have hx0 : x ≠ 0 := by
    intro h; rw [h] at hcard; simp at hcard
  have hprod : (∏ p ∈ x.primeFactors, (x.factorization p + 1)) = 3 := by
    rw [← Nat.card_divisors hx0]; exact hcard
  exact prod_three_implies_struct x hx0 hprod

end Problems.Minif2f.mathd_numbertheory_221
