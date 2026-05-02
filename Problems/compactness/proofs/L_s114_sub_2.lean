import Mathlib
import Problems.compactness.Defs

namespace Problems.compactness

theorem s114_sub_2 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    IsChain (· ⊆ ·) C →
    ∀ (a : PropForm α) (s : Set (PropForm α)),
    a ∈ ⋃₀ C → (∃ X ∈ C, s ⊆ X) →
    ∃ Z ∈ C, insert a s ⊆ Z := by
  intro α C hChain a s ha hs
  obtain ⟨Y, hY, haY⟩ := ha
  obtain ⟨X, hX, hsX⟩ := hs
  by_cases hXY : X = Y
  · refine ⟨Y, hY, ?_⟩
    intro z hz
    rcases Set.mem_insert_iff.mp hz with rfl | hzs
    · exact haY
    · exact hXY ▸ hsX hzs
  · rcases hChain hX hY hXY with hsub | hsub
    · refine ⟨Y, hY, ?_⟩
      intro z hz
      rcases Set.mem_insert_iff.mp hz with rfl | hzs
      · exact haY
      · exact hsub (hsX hzs)
    · refine ⟨X, hX, ?_⟩
      intro z hz
      rcases Set.mem_insert_iff.mp hz with rfl | hzs
      · exact hsub haY
      · exact hsX hzs

end Problems.compactness
