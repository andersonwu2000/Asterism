import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

/-- Zorn's lemma applied to the poset of finitely satisfiable supersets of S.
Given the chain-bound lemma, there exists a maximal finitely satisfiable M ⊇ S. -/
theorem s3_sub_2 {α : Type}
    (S : Set (PropForm α))
    (hS : ∀ T : Set (PropForm α), T ⊆ S → T.Finite → Sat T)
    (hchain_bound : ∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C →
        (∀ s ∈ C, ∀ T : Set (PropForm α), T ⊆ s → T.Finite → Sat T) →
        ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) :
    ∃ M : Set (PropForm α),
      S ⊆ M ∧
      (∀ T : Set (PropForm α), T ⊆ M → T.Finite → Sat T) ∧
      ∀ M' : Set (PropForm α), M ⊆ M' →
        (∀ T : Set (PropForm α), T ⊆ M' → T.Finite → Sat T) → M' ⊆ M := by sorry

end Problems.compactness
