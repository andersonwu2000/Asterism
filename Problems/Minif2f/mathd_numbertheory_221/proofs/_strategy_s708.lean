import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_three_div_iff_explicit

namespace Problems.Minif2f.mathd_numbertheory_221

-- Per-element characterization: x ∈ S iff x ∈ {4,9,25,49,121,169,289,361,529,841,961}.
-- Sub-goal abstracts the math content (numbers <1000 with 3 divisors = squares of
-- primes ≤ 31); parent then converts to set equality via Finset.ext and computes card.
theorem s708 : ∀ (S : Finset ℕ) (h₀ : ∀ x : ℕ, x ∈ S ↔ 0 < x ∧ x < 1000 ∧ x.divisors.card = 3), S.card = 11  := by
  intro S h₀
  have h_char := three_div_iff_explicit
  have h_eq : S = ({4, 9, 25, 49, 121, 169, 289, 361, 529, 841, 961} : Finset ℕ) := by
    apply Finset.ext
    intro x
    rw [h₀ x]
    exact h_char x
  rw [h_eq]
  decide

end Problems.Minif2f.mathd_numbertheory_221
