import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s11_s3_main_sub_4_sub_2 :
    ∀ {α : Type} (M : Set (PropForm α)) (v : Valuation α) (p : PropForm α),
    (∀ q : PropForm α, PropForm.neg q ∈ M ↔ q ∉ M) →
    (PropForm.eval v p = true ↔ p ∈ M) →
    (PropForm.eval v (PropForm.neg p) = true ↔ PropForm.neg p ∈ M) := by
  sorry

end Problems.compactness
