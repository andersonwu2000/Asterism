import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Truth Lemma: neg- and conj-closure of M implies existence of a valuation satisfying all of M.
theorem s1_sub_4 {α : Type} (M : Set (PropForm α))
    (hNeg  : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (hConj : ∀ φ ψ : PropForm α, PropForm.conj φ ψ ∈ M ↔ (φ ∈ M ∧ ψ ∈ M)) :
    ∃ v : Valuation α, ∀ φ : PropForm α, φ ∈ M → PropForm.eval v φ = true := by
  sorry

end Problems.compactness
