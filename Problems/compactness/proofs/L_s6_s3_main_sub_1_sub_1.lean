import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s6_s3_main_sub_1_sub_1 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    IsChain (· ⊆ ·) C →
    C.Nonempty →
    ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ C → ∃ N ∈ C, T ⊆ N := by
  intro α C hchain hne T hfin
  induction T, hfin using Set.Finite.induction_on with
  | empty =>
    intro _
    obtain ⟨N, hN⟩ := hne
    exact ⟨N, hN, Set.empty_subset _⟩
  | insert ha _ ih =>
    intro hsub
    have ha_mem : _ ∈ ⋃₀ C := hsub (Set.mem_insert _ _)
    have hs_sub : _ ⊆ ⋃₀ C := (Set.subset_insert _ _).trans hsub
    obtain ⟨N1, hN1C, hN1⟩ := ih hs_sub
    obtain ⟨N2, hN2C, hN2⟩ := Set.mem_sUnion.mp ha_mem
    by_cases heq : N1 = N2
    · exact ⟨N2, hN2C, Set.insert_subset hN2 (heq ▸ hN1)⟩
    · rcases hchain hN1C hN2C heq with h | h
      · exact ⟨N2, hN2C, Set.insert_subset hN2 (hN1.trans h)⟩
      · exact ⟨N1, hN1C, Set.insert_subset (h hN2) hN1⟩

end Problems.compactness
