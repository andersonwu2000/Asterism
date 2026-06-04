import Mathlib
import Problems.Minif2f.mathd_numbertheory_303.Defs
import Problems.Minif2f.mathd_numbertheory_303.proofs.L_cond_implies_in_set
import Problems.Minif2f.mathd_numbertheory_303.proofs.L_in_set_implies_cond

namespace Problems.Minif2f.mathd_numbertheory_303

-- Split the Finset equality into two membership directions and stitch via Finset.ext.
-- Sub-goal 1 (cond_implies_in_set): the predicate forces n ∈ {7,13,91}.
-- Sub-goal 2 (in_set_implies_cond): each of 7,13,91 satisfies the predicate (decidable).
-- Both directions are strictly simpler than the original Finset equality.
theorem s9347
    (S : Finset ℕ)
    (h₀ : ∀ n : ℕ, n ∈ S ↔ 2 ≤ n ∧ 171 ≡ 80 [MOD n] ∧ 468 ≡ 13 [MOD n]) :
    S = ({7, 13, 91} : Finset ℕ)  := by
  have h_fwd := cond_implies_in_set
  have h_bwd := in_set_implies_cond
  ext n
  rw [h₀]
  simp only [Finset.mem_insert, Finset.mem_singleton]
  exact ⟨h_fwd n, h_bwd n⟩

end Problems.Minif2f.mathd_numbertheory_303
