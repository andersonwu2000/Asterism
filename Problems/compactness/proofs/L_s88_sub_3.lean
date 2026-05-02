import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s91

namespace Problems.compactness

theorem s88_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (C : Set (Set (PropForm α))),
      C ⊆ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
      IsChain (· ⊆ ·) C →
      C.Nonempty →
      ∃ ub ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        ∀ z ∈ C, z ⊆ ub) →
    ∃ M : Set (PropForm α),
      (S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α),
        (S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        M ⊆ N → M = N := s91

end Problems.compactness
