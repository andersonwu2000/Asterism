import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s88_sub_2 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ (C : Set (Set (PropForm α))), C.Nonempty → IsChain (· ⊆ ·) C →
      (∀ X ∈ C, S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) →
    ∀ (C : Set (Set (PropForm α))),
      C ⊆ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T} →
      IsChain (· ⊆ ·) C →
      C.Nonempty →
      ∃ ub ∈ {X : Set (PropForm α) | S ⊆ X ∧ ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T},
        ∀ z ∈ C, z ⊆ ub := by
  intro α S h2 C hCP hChain hNonempty
  exact ⟨⋃₀ C, h2 C hNonempty hChain (fun X hX => hCP hX),
         fun z hz => Set.subset_sUnion_of_mem hz⟩

end Problems.compactness
