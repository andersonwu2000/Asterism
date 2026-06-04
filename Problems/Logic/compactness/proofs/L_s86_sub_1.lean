import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s86_sub_1 : ∀ {α : Type} (S : Set (PropForm α)),
    (∀ (C : Set (Set (PropForm α))),
      C.Nonempty →
      IsChain (· ⊆ ·) C →
      (∀ X ∈ C, ∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T) →
      ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) →
    ∀ (C : Set (Set (PropForm α))),
      C.Nonempty →
      IsChain (· ⊆ ·) C →
      (∀ X ∈ C, S ⊆ X ∧ (∀ T : Set (PropForm α), T ⊆ X → T.Finite → Sat T)) →
      S ⊆ ⋃₀ C ∧ (∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T) := by
  intro α S h2 C hne hchain hC
  constructor
  · obtain ⟨X₀, hX₀⟩ := hne
    exact (hC X₀ hX₀).1.trans (Set.subset_sUnion_of_mem hX₀)
  · exact h2 C hne hchain (fun X hX => (hC X hX).2)

end Problems.Logic.compactness
