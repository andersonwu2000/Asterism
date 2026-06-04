import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s88_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T) →
    S ⊆ S ∧ ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T := by
  intro α S h
  exact ⟨Set.Subset.refl S, h⟩

end Problems.Logic.compactness
