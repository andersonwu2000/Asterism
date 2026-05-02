import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s115

namespace Problems.compactness

theorem s91_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    S ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} := s115

end Problems.compactness
