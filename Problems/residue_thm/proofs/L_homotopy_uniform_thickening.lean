import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- homotopy_uniform_thickening: uniform δ-thickening of compact image H([0,1]²) fits inside open U
-- Uses IsCompact.exists_thickening_subset_open (compactness of [0,1]² → compact image → uniform δ).
theorem homotopy_uniform_thickening
    {U : Set ℂ} {H : ℝ → ℝ → ℂ}
    (hU : IsOpen U)
    (hHcont : ContinuousOn (Function.uncurry H) (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHmaps : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ U) :
    ∃ δ : ℝ, 0 < δ ∧
      ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1,
        Metric.ball (H τ t) δ ⊆ U := by
  have hK : IsCompact (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) := isCompact_Icc.prod isCompact_Icc
  have hKim : IsCompact ((Function.uncurry H) '' (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1)) :=
    hK.image_of_continuousOn hHcont
  have hKU : (Function.uncurry H) '' (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) ⊆ U := by
    rintro z ⟨⟨τ, t⟩, ⟨hτ, ht⟩, rfl⟩
    exact hHmaps τ hτ t ht
  obtain ⟨δ, hδ, hthick⟩ := hKim.exists_thickening_subset_open hU hKU
  refine ⟨δ, hδ, fun τ hτ t ht z hz => hthick ?_⟩
  have hHτt : H τ t ∈ (Function.uncurry H) '' (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1) :=
    ⟨(τ, t), Set.mk_mem_prod hτ ht, rfl⟩
  rw [Metric.mem_thickening_iff]
  exact ⟨H τ t, hHτt, Metric.mem_ball.mp hz⟩

end Problems.residue_thm

