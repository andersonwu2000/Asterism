import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_factorization_eq_single_of_struct
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_three_div_implies_prime_factor_struct

namespace Problems.Minif2f.mathd_numbertheory_221

-- Decompose `card_divisors = 3 → factorization = Finsupp.single p 2` into
-- (a) structural extraction: `primeFactors = {p}` + `factorization p = 2` from the
-- divisor-count hypothesis, and (b) Finsupp manipulation: any factorization with
-- support `{p}` and value 2 equals `Finsupp.single p 2` (no divisor-count needed).
theorem s9659 :
    ∀ x : ℕ, x.divisors.card = 3 →
      ∃ p : ℕ, p.Prime ∧ x.factorization = Finsupp.single p 2  := by
  intro x hx
  obtain ⟨p, hp_prime, hp_supp, hp_val⟩ :=
    three_div_implies_prime_factor_struct x hx
  exact ⟨p, hp_prime, factorization_eq_single_of_struct x p hp_supp hp_val⟩

end Problems.Minif2f.mathd_numbertheory_221
