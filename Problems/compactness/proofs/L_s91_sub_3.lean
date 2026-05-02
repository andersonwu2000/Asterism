import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s116

namespace Problems.compactness

theorem s91_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∃ M ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
      ∀ N ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        M ⊆ N → N = M) →
    ∃ M : Set (PropForm α),
      (S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α),
        (S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        M ⊆ N → M = N := s116

end Problems.compactness
