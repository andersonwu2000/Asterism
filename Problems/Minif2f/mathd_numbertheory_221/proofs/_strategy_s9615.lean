import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_pow_two_of_fact_eq_single
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_three_div_implies_fact_eq_single

namespace Problems.Minif2f.mathd_numbertheory_221

-- Decompose `card_divisors = 3 → x = p^2` via prime factorization.
-- Sub 1 (`three_div_implies_fact_eq_single`): `card_divisors = 3` forces
--   the factorization Finsupp to be `Finsupp.single p 2` for a prime `p`.
-- Sub 2 (`pow_two_of_fact_eq_single`): reconstruct `x = p^2` from that
--   factorization (uses `Nat.prod_factorization_pow_eq_self`).
theorem s9615 :
    ∀ x : ℕ, x.divisors.card = 3 → ∃ p : ℕ, p.Prime ∧ x = p^2  := by
  intro x hx
  have h1 := three_div_implies_fact_eq_single x hx
  obtain ⟨p, hp, hfact⟩ := h1
  have h2 := pow_two_of_fact_eq_single x p hp hfact
  exact ⟨p, hp, h2⟩

end Problems.Minif2f.mathd_numbertheory_221

