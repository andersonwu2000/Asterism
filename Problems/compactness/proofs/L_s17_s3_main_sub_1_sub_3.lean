import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Given the cover lemma, a nonempty chain of finitely-satisfiable supersets of S
-- has a finsat sUnion that still contains S.
-- S ⊆ ⋃₀ C: pick any element of the nonempty chain.
-- Finsat: any finite T ⊆ ⋃₀ C lies in some chain element by the cover lemma.
theorem s17_s3_main_sub_1_sub_3 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ (C : Set (Set (PropForm α))), IsChain (· ⊆ ·) C → C.Nonempty →
        ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ C → ∃ X ∈ C, T ⊆ X) →
    ∀ C : Set (Set (PropForm α)), IsChain (· ⊆ ·) C → C.Nonempty →
        (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
        S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T := by
  sorry

end Problems.compactness
