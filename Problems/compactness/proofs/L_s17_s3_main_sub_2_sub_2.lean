import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s17_s3_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)) (p : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∃ T' : Set (PropForm α), T' ⊆ M ∧ T'.Finite ∧ ¬Sat (T' ∪ {p})) →
    ∀ T : Set (PropForm α), T ⊆ M ∪ {PropForm.neg p} → T.Finite → Sat T := by
  sorry

end Problems.compactness
