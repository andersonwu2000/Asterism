import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s87

namespace Problems.compactness

theorem s78_sub_2 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    C.Nonempty →
    IsChain (· ⊆ ·) C →
    (∀ X ∈ C, ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
    ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T := s87

end Problems.compactness
