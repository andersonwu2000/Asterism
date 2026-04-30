import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s13_s3_main_sub_1_sub_2 : ∀ {α : Type} (S : Set (PropForm α))
    (C : Set (Set (PropForm α))),
    (∀ (C' : Set (Set (PropForm α))) (T : Set (PropForm α)),
        IsChain (· ⊆ ·) C' → C'.Nonempty → T.Finite → T ⊆ ⋃₀ C' → ∃ M ∈ C', T ⊆ M) →
    IsChain (· ⊆ ·) C →
    C.Nonempty →
    (∀ M ∈ C, S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) →
    ∃ ub : Set (PropForm α),
      (S ⊆ ub ∧ ∀ T : Set (PropForm α), T ⊆ ub → T.Finite → Sat T) ∧
      ∀ M ∈ C, M ⊆ ub := by
  sorry

end Problems.compactness
