import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s23_s4_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') →
    ∀ p : PropForm α, p ∉ M →
    ∃ U : Set (PropForm α), U ⊆ M ∧ U.Finite ∧ ¬Sat (U ∪ {p}) := by
  sorry

end Problems.compactness
