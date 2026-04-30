import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s16_s3_main_sub_2_sub_1 : ∀ {α : Type} (M : Set (PropForm α)) (p : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ¬(∀ T : Set (PropForm α), T ⊆ M ∪ {p} → T.Finite → Sat T) →
    ∀ T : Set (PropForm α), T ⊆ M ∪ {PropForm.neg p} → T.Finite → Sat T := by
  sorry

end Problems.compactness
