import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s114

namespace Problems.compactness

theorem s87_sub_1 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    C.Nonempty →
    IsChain (· ⊆ ·) C →
    ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite →
    ∃ X ∈ C, T ⊆ X := s114

end Problems.compactness
