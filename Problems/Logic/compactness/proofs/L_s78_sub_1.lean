import Mathlib
import Problems.Logic.compactness.Defs

namespace Problems.Logic.compactness

theorem s78_sub_1 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    C.Nonempty →
    IsChain (· ⊆ ·) C →
    ∀ T : Set (PropForm α), T.Finite → T ⊆ ⋃₀ C →
    ∃ X ∈ C, T ⊆ X := by
  intro α C hne hchain T hfin
  refine Set.Finite.induction_on T hfin ?_ ?_
  · intro _
    exact ⟨hne.choose, hne.choose_spec, Set.empty_subset _⟩
  · intro a s ha hs ih hsub
    have ha_in : a ∈ ⋃₀ C := hsub (Set.mem_insert_iff.mpr (Or.inl rfl))
    obtain ⟨Xa, hXa, haXa⟩ := Set.mem_sUnion.mp ha_in
    obtain ⟨Xs, hXs, hsXs⟩ := ih (fun x hx => hsub (Set.mem_insert_iff.mpr (Or.inr hx)))
    rcases eq_or_ne Xa Xs with rfl | hne'
    · exact ⟨Xa, hXa, Set.insert_subset_iff.mpr ⟨haXa, hsXs⟩⟩
    · rcases hchain hXa hXs hne' with h | h
      · exact ⟨Xs, hXs, Set.insert_subset_iff.mpr ⟨h haXa, hsXs⟩⟩
      · exact ⟨Xa, hXa, Set.insert_subset_iff.mpr ⟨haXa, hsXs.trans h⟩⟩

end Problems.Logic.compactness
