import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s88

namespace Problems.compactness

theorem s86_sub_2 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (C : Set (Set (PropForm α))),
      C.Nonempty →
      IsChain (· ⊆ ·) C →
      (∀ X ∈ C, S ⊆ X ∧ (∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T)) →
      S ⊆ ⋃₀ C ∧ (∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T)) →
    ∃ M : Set (PropForm α),
      (S ⊆ M ∧ (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T)) ∧
      ∀ N : Set (PropForm α),
        (S ⊆ N ∧ (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T)) →
        M ⊆ N → M = N := s88

end Problems.compactness
