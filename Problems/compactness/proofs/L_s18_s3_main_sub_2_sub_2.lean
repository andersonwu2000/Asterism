import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s18_s3_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)) (q : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ¬(∀ T : Set (PropForm α), T ⊆ M ∪ {q} → T.Finite → Sat T) →
    ∃ T₀ : Set (PropForm α), T₀ ⊆ M ∧ T₀.Finite ∧ ¬Sat (T₀ ∪ {q}) := by
  sorry

end Problems.compactness
