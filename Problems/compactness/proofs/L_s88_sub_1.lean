import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s88_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T := by
  intro α S h
  exact ⟨Set.Subset.refl S, h⟩

end Problems.compactness
