import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s14_s3_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ c : Set (Set (PropForm α)), c.Nonempty → IsChain (· ⊆ ·) c →
      (∀ M ∈ c, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  sorry

end Problems.compactness
