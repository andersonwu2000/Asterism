import Mathlib
import Problems.compactness.Defs
import Problems.compactness.proofs.L_s114_sub_1
import Problems.compactness.proofs.L_s114_sub_2

namespace Problems.compactness

theorem s114 : ∀ {α : Type} (C : Set (Set (PropForm α))),
    C.Nonempty →
    IsChain (· ⊆ ·) C →
    ∀ T : Set (PropForm α), T ⊆ ⋃₀ C → T.Finite →
    ∃ X ∈ C, T ⊆ X := by
  intro α C hCne hChain T hTC hTfin
  classical
  suffices H : ∀ F : Finset (PropForm α),
      (↑F : Set (PropForm α)) ⊆ ⋃₀ C →
      ∃ X ∈ C, (↑F : Set (PropForm α)) ⊆ X by
    have hcoe : (↑hTfin.toFinset : Set (PropForm α)) = T := hTfin.coe_toFinset
    have hsub : (↑hTfin.toFinset : Set (PropForm α)) ⊆ ⋃₀ C := by
      rw [hcoe]; exact hTC
    obtain ⟨X, hXC, hX⟩ := H hTfin.toFinset hsub
    refine ⟨X, hXC, ?_⟩
    rw [← hcoe]
    exact hX
  intro F
  induction F using Finset.induction_on with
  | empty =>
    intro _
    obtain ⟨X, hXC, hX⟩ := s114_sub_1 C hCne
    refine ⟨X, hXC, ?_⟩
    rw [Finset.coe_empty]
    exact hX
  | @insert a F' _ ih =>
    intro hFsub
    rw [Finset.coe_insert] at hFsub
    have hsubF' : (↑F' : Set (PropForm α)) ⊆ ⋃₀ C :=
      (Set.subset_insert a _).trans hFsub
    have haUC : a ∈ ⋃₀ C := hFsub (Set.mem_insert_iff.mpr (Or.inl rfl))
    obtain ⟨Z, hZC, hZ⟩ :=
      s114_sub_2 C hChain a (↑F' : Set (PropForm α)) haUC (ih hsubF')
    refine ⟨Z, hZC, ?_⟩
    rw [Finset.coe_insert]
    exact hZ

end Problems.compactness
