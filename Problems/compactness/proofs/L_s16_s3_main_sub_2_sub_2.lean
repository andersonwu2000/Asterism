import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s16_s3_main_sub_2_sub_2 : ∀ {α : Type} (M : Set (PropForm α)) (p : PropForm α),
    (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    (∀ N : Set (PropForm α), M ⊆ N →
      (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N) →
    (∀ T : Set (PropForm α), T ⊆ M ∪ {p} → T.Finite → Sat T) →
    p ∈ M := by
  sorry

end Problems.compactness
