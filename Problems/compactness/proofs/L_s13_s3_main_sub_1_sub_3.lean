import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s13_s3_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ C : Set (Set (PropForm α)),
        IsChain (· ⊆ ·) C →
        C.Nonempty →
        (∀ M ∈ C, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
        ∃ ub : Set (PropForm α),
          (S ⊆ ub ∧ ∀ T : Set (PropForm α), T ⊆ ub → T.Finite → Sat T) ∧
          ∀ M ∈ C, M ⊆ ub) →
    ∃ M : Set (PropForm α), S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := by
  sorry

end Problems.compactness
