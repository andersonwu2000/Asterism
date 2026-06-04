import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_factorization_eq_two_of_singleton
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_prod_three_primefactors_singleton

namespace Problems.Minif2f.mathd_numbertheory_221

-- Decompose `(∏ p ∈ primeFactors, factorization p + 1) = 3 → ∃ p, singleton + multiplicity 2`
-- into (1) `prod_three_primefactors_singleton`: the product-3 forces primeFactors to be a
-- singleton `{p}` with `p` prime, and (2) `factorization_eq_two_of_singleton`: when the
-- support is a singleton and the product is 3, the unique multiplicity must be 2.
-- Each sub-goal is strictly simpler: (1) drops the multiplicity-extraction concern;
-- (2) has the singleton hypothesis as a strengthened input, reducing the product to a
-- single factor `factorization p + 1 = 3`.
theorem s9743 :
    ∀ y : ℕ, y ≠ 0 →
      (∏ p ∈ y.primeFactors, (y.factorization p + 1)) = 3 →
      ∃ p : ℕ, p.Prime ∧ y.primeFactors = {p} ∧ y.factorization p = 2  := by
  intro y hy0 hprod
  have h_sing : ∃ p : ℕ, p.Prime ∧ y.primeFactors = {p} :=
    prod_three_primefactors_singleton y hy0 hprod
  obtain ⟨p, hp, hsing⟩ := h_sing
  have h_two : y.factorization p = 2 :=
    factorization_eq_two_of_singleton y p hy0 hsing hprod
  exact ⟨p, hp, hsing, h_two⟩

end Problems.Minif2f.mathd_numbertheory_221
