import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s6_s3_main_sub_1_sub_2 : ∀ {α : Type} (S : Set (PropForm α))
    (C : Set (Set (PropForm α))),
    IsChain (· ⊆ ·) C →
    C.Nonempty →
    (∀ N ∈ C, S ⊆ N ∧ ∀ T : Set (PropForm α), T ⊆ N → T.Finite → Sat T) →
    (∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ C → ∃ N ∈ C, T ⊆ N) →
    S ⊆ ⋃₀ C ∧ ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite → Sat T := by
  intro α S C _hchain hne hsat hcover
  constructor
  · obtain ⟨N₀, hN₀⟩ := hne
    exact ((hsat N₀ hN₀).1).trans (Set.subset_sUnion_of_mem hN₀)
  · intro T hT hfin
    obtain ⟨N, hN, hTN⟩ := hcover T hfin hT
    exact (hsat N hN).2 T hTN hfin

end Problems.compactness
