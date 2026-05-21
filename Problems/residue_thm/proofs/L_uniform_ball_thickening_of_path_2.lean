import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- uniform_ball_thickening_of_path_2: compact image + IsCompact.exists_thickening_subset_open gives
-- uniform δ; ball_subset_thickening converts to the per-point ball condition.
theorem uniform_ball_thickening_of_path_2
    {U : Set ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U) :
    ∃ δ : ℝ, 0 < δ ∧ ∀ t ∈ Set.Icc (0:ℝ) 1, Metric.ball (γ t) δ ⊆ U := by
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have hK : IsCompact (γ '' Set.Icc 0 1) := isCompact_Icc.image_of_continuousOn hγcont
  have hKsubU : γ '' Set.Icc 0 1 ⊆ U := hmaps.image_subset
  obtain ⟨δ, hδpos, hδ⟩ := hK.exists_thickening_subset_open hU hKsubU
  exact ⟨δ, hδpos, fun t ht z hz =>
    hδ (Metric.ball_subset_thickening (Set.mem_image_of_mem γ ht) δ hz)⟩

end Problems.residue_thm
