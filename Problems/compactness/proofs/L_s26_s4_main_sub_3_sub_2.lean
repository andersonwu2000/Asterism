import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s26_s4_main_sub_3_sub_2 {α : Type} (M : Set (PropForm α))
    (hfinsat : ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)
    (hneg : ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M)
    (p q : PropForm α) (hconj : PropForm.conj p q ∈ M) : q ∈ M := by sorry

end Problems.compactness
