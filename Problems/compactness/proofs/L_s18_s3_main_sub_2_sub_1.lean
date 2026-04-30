import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s18_s3_main_sub_2_sub_1 : ∀ {α : Type} (M : Set (PropForm α)) (q : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), M ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) →
    q ∉ M →
    ¬(∀ T : Set (PropForm α), T ⊆ M ∪ {q} → T.Finite → Sat T) := by
  sorry

end Problems.compactness
