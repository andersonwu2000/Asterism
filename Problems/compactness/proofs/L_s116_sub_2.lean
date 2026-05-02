import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s116_sub_2 : ∀ {α : Type} (S M : Set (PropForm α)),
    (∀ N ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
      M ⊆ N → N = M) →
    ∀ N : Set (PropForm α),
      (S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
      M ⊆ N → M = N := by
  intro α S M hMmax N hN hMN
  exact (hMmax N hN hMN).symm

end Problems.compactness
