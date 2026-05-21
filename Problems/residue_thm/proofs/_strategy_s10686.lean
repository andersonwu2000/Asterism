import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Direct FTC. For `t ∈ Ioo (1/2) 1`, `Icc (1/2) 1 ∈ 𝓝 t` upgrades the
-- `ContinuousOn` hypothesis to `ContinuousAt g t`, `IntervalIntegrable g (1/2) t`,
-- and `StronglyMeasurableAtFilter g (𝓝 t)` (via `isOpen_Ioo`); then apply
-- `intervalIntegral.integral_hasDerivAt_right` + `HasDerivAt.const_add C`.
theorem s10686 {g : ℝ → ℂ}
    (hg : ContinuousOn g (Set.Icc (1/2 : ℝ) 1)) (C : ℂ) :
    ∀ t ∈ Set.Ioo (1/2 : ℝ) 1,
      HasDerivAt (fun u : ℝ => C + ∫ s in ((1:ℝ)/2)..u, g s) (g t) t  := by
  intro t ht
  have hIcc : Set.Icc (1/2 : ℝ) 1 ∈ nhds t := Icc_mem_nhds ht.1 ht.2
  have ht_mem : t ∈ Set.Icc (1/2 : ℝ) 1 := ⟨ht.1.le, ht.2.le⟩
  have hCt : ContinuousAt g t := (hg t ht_mem).continuousAt hIcc
  have hII : IntervalIntegrable g MeasureTheory.volume (1/2) t :=
    (hg.mono (Set.Icc_subset_Icc_right ht.2.le)).intervalIntegrable_of_Icc ht.1.le
  have hSMF : StronglyMeasurableAtFilter g (nhds t) MeasureTheory.volume :=
    (hg.mono Set.Ioo_subset_Icc_self).stronglyMeasurableAtFilter isOpen_Ioo t ht
  have hDR : HasDerivAt (fun u => ∫ s in ((1:ℝ)/2)..u, g s) (g t) t :=
    intervalIntegral.integral_hasDerivAt_right hII hSMF hCt
  exact hDR.const_add C

end Problems.residue_thm
