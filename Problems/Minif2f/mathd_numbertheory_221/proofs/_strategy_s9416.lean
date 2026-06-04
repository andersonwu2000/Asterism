import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_prime_sq_lt_1000_in_set
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_three_div_implies_prime_sq

namespace Problems.Minif2f.mathd_numbertheory_221

-- Forward direction: 3 divisors + x<1000 ⇒ x is in the set.
-- Sub-goal 1 (`three_div_implies_prime_sq`): 3 divisors ⇒ x = p² for some prime p.
-- Sub-goal 2 (`prime_sq_lt_1000_in_set`): p prime ∧ p² < 1000 ⇒ p² ∈ {4,9,…,961}.
-- Combine via `obtain ⟨p, hp, rfl⟩` then apply sub-goal 2.
set_option linter.style.longLine false in
theorem s9416 : ∀ x : ℕ, (0 < x ∧ x < 1000 ∧ x.divisors.card = 3) → x ∈ ({4, 9, 25, 49, 121, 169, 289, 361, 529, 841, 961} : Finset ℕ)  := by
  intro x ⟨_hx_pos, hx_lt, hx_div⟩
  obtain ⟨p, hp, rfl⟩ := three_div_implies_prime_sq x hx_div
  exact prime_sq_lt_1000_in_set p hp hx_lt

end Problems.Minif2f.mathd_numbertheory_221
