import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- pairwise_pole_lower_bound: Finset.offDiag minimum gives a positive pairwise-distance lower bound
theorem pairwise_pole_lower_bound
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ} (r : ℂ → ℝ)
    (hr_pos : ∀ a ∈ T, 0 < r a)
    (hγC : ContinuousOn γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ d : ℝ, 0 < d ∧ ∀ a ∈ T, ∀ b ∈ T, a ≠ b → d ≤ dist a b := by
  by_cases hT : T.offDiag.Nonempty
  · let S := T.offDiag.image (fun p => dist p.1 p.2)
    have hS_nonempty : S.Nonempty := hT.image _
    have hS_pos : ∀ d ∈ S, 0 < d := by
      intro d hd
      obtain ⟨⟨a, b⟩, hab, rfl⟩ := Finset.mem_image.mp hd
      rw [Finset.mem_offDiag] at hab
      exact dist_pos.mpr hab.2.2
    exact ⟨S.min' hS_nonempty, hS_pos _ (Finset.min'_mem S hS_nonempty),
           fun a ha b hb hab =>
             Finset.min'_le S _ (Finset.mem_image.mpr
               ⟨(a, b), Finset.mem_offDiag.mpr ⟨ha, hb, hab⟩, rfl⟩)⟩
  · exact ⟨1, one_pos, fun a ha b hb hab =>
      absurd ⟨(a, b), Finset.mem_offDiag.mpr ⟨ha, hb, hab⟩⟩ hT⟩

end Problems.residue_thm
