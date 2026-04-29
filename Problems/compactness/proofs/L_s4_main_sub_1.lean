import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s4_main_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M' := by
  sorry

end Problems.compactness
