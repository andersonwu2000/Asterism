import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integrable_f_along_gamma: ContinuousOn.intervalIntegrable_of_Icc via derivWithin + ae congr
-- Prove integrability using derivWithin (continuous by ContDiffOn.continuousOn_derivWithin),
-- then swap to deriv via ae equality on Ioo 0 1 where Icc 0 1 is a full neighbourhood.
theorem integrable_f_along_gamma
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    IntervalIntegrable (fun t => f (γ t) * deriv γ t) MeasureTheory.volume 0 1 := by
  have huniq : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1) := uniqueDiffOn_Icc (by norm_num)
  have hint : IntervalIntegrable (fun t => f (γ t) * derivWithin γ (Set.Icc (0:ℝ) 1) t)
      MeasureTheory.volume 0 1 :=
    ContinuousOn.intervalIntegrable_of_Icc (by norm_num)
      ((hf.continuousOn.comp hγ.continuousOn hmap).mul
        (hγ.continuousOn_derivWithin huniq le_rfl))
  apply hint.congr_ae
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
  change ∀ᵐ t ∂MeasureTheory.volume.restrict (Set.Ioc (0:ℝ) 1),
      f (γ t) * derivWithin γ (Set.Icc 0 1) t = f (γ t) * deriv γ t
  rw [MeasureTheory.ae_restrict_iff' measurableSet_Ioc]
  have hne1 : ∀ᵐ t ∂MeasureTheory.volume, t ≠ (1:ℝ) := by
    rw [MeasureTheory.ae_iff]
    simp
  filter_upwards [hne1] with t ht1 ht2
  simp only [Set.mem_Ioc] at ht2
  have htint : t ∈ Set.Ioo (0:ℝ) 1 := ⟨ht2.1, lt_of_le_of_ne ht2.2 ht1⟩
  congr 1
  exact derivWithin_of_mem_nhds (f := γ) (Icc_mem_nhds htint.1 htint.2)

end Problems.residue_thm
