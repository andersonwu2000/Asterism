import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

-- Given the chain cover lemma, a nonempty chain of finitely-satisfiable supersets of S
-- has a finitely-satisfiable sUnion that still contains S.
theorem s13_s3_main_sub_1_sub_2 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ (c' : Set (Set (PropForm α))), c'.Nonempty → IsChain (· ⊆ ·) c' →
      ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ c' → ∃ X ∈ c', T ⊆ X) →
    ∀ c : Set (Set (PropForm α)), c.Nonempty → IsChain (· ⊆ ·) c →
      (∀ X ∈ c, S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      S ⊆ ⋃₀ c ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ c → T.Finite → Sat T := by
  intro α S hcover c hnonempty hchain hc
  constructor
  · obtain ⟨X, hX⟩ := hnonempty
    exact (hc X hX).1.trans (Set.subset_sUnion_of_mem hX)
  · intro T hT hTfin
    obtain ⟨X, hXc, hTX⟩ := hcover c hnonempty hchain T hTfin hT
    exact (hc X hXc).2 T hTX hTfin

end Problems.compactness
