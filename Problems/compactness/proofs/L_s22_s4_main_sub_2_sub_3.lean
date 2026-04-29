import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s22_s4_main_sub_2_sub_3 : ∀ {α : Type} (M : Set (PropForm α)) (p : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ¬(∀ T : Set (PropForm α), T ⊆ insert p M → T.Finite → Sat T) →
    ∃ T₀ : Set (PropForm α), T₀ ⊆ M ∧ T₀.Finite ∧ ¬Sat (insert p T₀) := by
  sorry

end Problems.compactness
