import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s15_s3_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ c : Set (Set (PropForm α)),
      (∀ M ∈ c, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
      IsChain (· ⊆ ·) c → c.Nonempty →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  sorry

end Problems.compactness
