import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- uniform_ball_thickening_of_path: compact image of γ in open U admits uniform δ-thickening
-- Uses IsCompact.exists_thickening_subset_open + ball_subset_thickening
theorem uniform_ball_thickening_of_path
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U) :
    ∃ δ : ℝ, 0 < δ ∧ ∀ t ∈ Set.Icc (0:ℝ) 1, Metric.ball (γ t) δ ⊆ U := by
  have hcomp : IsCompact (γ '' Set.Icc 0 1) :=
    isCompact_Icc.image_of_continuousOn hγ.continuousOn
  obtain ⟨δ, hδ_pos, hδ⟩ :=
    hcomp.exists_thickening_subset_open hU hmaps.image_subset
  exact ⟨δ, hδ_pos, fun t ht =>
    (Metric.ball_subset_thickening (Set.mem_image_of_mem γ ht) δ).trans hδ⟩

end Problems.residue_thm
