import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s21_s4_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ M' : Set (PropForm α), M ⊆ M' →
      (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M = M') →
    ∀ q : PropForm α, q ∉ M →
      ∃ T : Set (PropForm α), T ⊆ M ∧ T.Finite ∧ ¬Sat (T ∪ {q}) := by
  sorry

end Problems.compactness
