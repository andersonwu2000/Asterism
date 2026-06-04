import Mathlib
import Problems.Minif2f.mathd_numbertheory_221.Defs
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_in_set_implies_three_div
import Problems.Minif2f.mathd_numbertheory_221.proofs.L_three_div_implies_in_set

namespace Problems.Minif2f.mathd_numbertheory_221

-- Split iff into forward (3 divisors → in the 11-element set) and backward (in set → 3 divisors).
-- Forward enumerates p²<1000 for prime p; backward is purely concrete (decide on each element).
theorem s9269 : ∀ x : ℕ, (0 < x ∧ x < 1000 ∧ x.divisors.card = 3) ↔ x ∈ ({4, 9, 25, 49, 121, 169, 289, 361, 529, 841, 961} : Finset ℕ)  := by
  intro x
  have h_fwd := three_div_implies_in_set x
  have h_bwd := in_set_implies_three_div x
  exact ⟨h_fwd, h_bwd⟩

end Problems.Minif2f.mathd_numbertheory_221
