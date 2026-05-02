import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s116_sub_1 : ∀ {α : Type} (S M : Set (PropForm α)),
    M ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
    S ⊆ M ∧ ∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T := by
  intro α S M hM
  exact hM

end Problems.compactness
