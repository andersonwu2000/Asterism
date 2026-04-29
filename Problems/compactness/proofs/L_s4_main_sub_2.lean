import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s4_main_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') →
    ∀ p : PropForm α, PropForm.neg p ∈ M ↔ p ∉ M := by
  sorry

end Problems.compactness
