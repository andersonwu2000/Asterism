import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s4_main_sub_4 : ∀ {α : Type} (S M : Set (PropForm α)),
    S ⊆ M →
    (∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M) →
    (∀ p q : PropForm α, PropForm.conj p q ∈ M ↔ (p ∈ M ∧ q ∈ M)) →
    Sat S := by
  sorry

end Problems.compactness
