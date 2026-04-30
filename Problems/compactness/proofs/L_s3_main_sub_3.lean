import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s3_main_sub_3 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ p : PropForm α, p ∈ M ∨ PropForm.neg p ∈ M) →
    ∃ v : Valuation α, ∀ p : PropForm α, p ∈ M ↔ PropForm.eval v p = true := by
  sorry

end Problems.compactness
