import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s86

namespace Problems.compactness

theorem s78_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    (∀ (C : Set (Set (PropForm α))),
      C.Nonempty →
      IsChain (· ⊆ ·) C →
      (∀ X ∈ C, ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) →
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ N : Set (PropForm α), M ⊆ N →
        (∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) → M = N := s86

end Problems.compactness
