import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem main : ∀ {α : Type} (S : Set (PropForm α)), (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) → Sat S := by sorry

end Problems.compactness
