import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Given the chain cover lemma, a nonempty chain of finitely-satisfiable supersets of S
-- has a finitely-satisfiable sUnion that still contains S.
theorem s18_s4_main_sub_1_sub_2 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ (c' : Set (Set (PropForm α))), c'.Nonempty → IsChain (· ⊆ ·) c' →
      ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c' → ∃ X ∈ c', T ⊆ X) →
    ∀ c : Set (Set (PropForm α)), c.Nonempty → IsChain (· ⊆ ·) c →
      (∀ X ∈ c, S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T := by
  sorry

end Problems.compactness
