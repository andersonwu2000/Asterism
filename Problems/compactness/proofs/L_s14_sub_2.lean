import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

open Classical

-- Neg step of the truth-lemma induction: given IH for φ and hNeg, the neg case holds.
theorem s14_sub_2 {α : Type} (M : Set (PropForm α))
    (hNeg : ∀ φ : PropForm α, PropForm.neg φ ∈ M ↔ φ ∉ M)
    (v : Valuation α) (φ : PropForm α)
    (ih : φ ∈ M ↔ PropForm.eval v φ = true) :
    PropForm.neg φ ∈ M ↔ PropForm.eval v (PropForm.neg φ) = true := by
  sorry

end Problems.compactness
