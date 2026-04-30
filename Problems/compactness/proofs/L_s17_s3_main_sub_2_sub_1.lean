import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s17_s3_main_sub_2_sub_1 : ∀ {α : Type} (M : Set (PropForm α)) (p : PropForm α),
    p ∉ M →
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), M ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) →
    ∃ T' : Set (PropForm α), T' ⊆ M ∧ T'.Finite ∧ ¬Sat (T' ∪ {p}) := by
  sorry

end Problems.compactness
