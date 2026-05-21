import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- infdist_gamma_image_pos: infDist from poles to compact curve image is positive
-- Uses IsCompact.image_of_continuousOn + IsClosed.notMem_iff_infDist_pos;
-- key: γ maps into U \ T so no pole a ∈ T lies in the image, and the image is compact (closed).
-- entry_kind: Builder
theorem infdist_gamma_image_pos
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ} (r : ℂ → ℝ)
    (hr_pos : ∀ a ∈ T, 0 < r a)
    (hγC : ContinuousOn γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∀ a ∈ T, 0 < Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) := by
  intro a haT
  have hcompact : IsCompact (γ '' Set.Icc (0:ℝ) 1) := isCompact_Icc.image_of_continuousOn hγC
  have ha_not_mem : a ∉ γ '' Set.Icc (0:ℝ) 1 := by
    rintro ⟨t, ht, rfl⟩
    exact (hγU ht).2 haT
  have hclosed : IsClosed (γ '' Set.Icc (0:ℝ) 1) := hcompact.isClosed
  have hnonempty : (γ '' Set.Icc (0:ℝ) 1).Nonempty :=
    ⟨γ 0, Set.mem_image_of_mem γ (Set.left_mem_Icc.mpr zero_le_one)⟩
  exact hclosed.notMem_iff_infDist_pos hnonempty |>.mp ha_not_mem

end Problems.residue_thm

