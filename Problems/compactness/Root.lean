import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs._strategy_s77

namespace Problems.compactness

theorem main : ∀ {α : Type} (S : Set (PropForm α)), (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := s77

end Problems.compactness
