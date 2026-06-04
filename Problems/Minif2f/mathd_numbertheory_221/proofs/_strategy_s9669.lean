import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_factor_struct_implies_single
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_three_div_implies_factor_struct

namespace Problems.Minif2f.mathd_numbertheory_221

-- Decompose `card_divisors = 3 → factorization = Finsupp.single p 2` into
-- (a) structural extraction `three_div_implies_factor_struct`: the divisor-count
--     hypothesis forces `primeFactors = {p}` together with `factorization p = 2`,
-- (b) Finsupp manipulation `factor_struct_implies_single`: a factorization with
--     support `{p}` and value `2` equals `Finsupp.single p 2` (no count needed).
-- Sub-goal (a) is strictly simpler — it stops at the structural facts, deferring
-- the Finsupp normalization. Sub-goal (b) is pure Finsupp/support algebra and
-- drops the `card_divisors = 3` hypothesis entirely.
theorem s9669 :
    ∀ x : ℕ, x.divisors.card = 3 →
      ∃ p : ℕ, p.Prime ∧ x.factorization = Finsupp.single p 2  := by
  intro x hx
  obtain ⟨p, hp_prime, hp_supp, hp_val⟩ := three_div_implies_factor_struct x hx
  exact ⟨p, hp_prime, factor_struct_implies_single x p hp_supp hp_val⟩

end Problems.Minif2f.mathd_numbertheory_221
