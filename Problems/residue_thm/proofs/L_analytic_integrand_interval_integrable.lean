import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- analytic_integrand_interval_integrable: continuity of g∘γ and derivWithin γ on Icc 0 1
-- gives IntervalIntegrable for the derivWithin version; congr_ae swaps to deriv γ using
-- derivWithin = deriv on Ioo 0 1 (a.e. in Ioc 0 1, excluding the measure-zero point {1}).
theorem analytic_integrand_interval_integrable
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U) :
    IntervalIntegrable (fun t => g (γ t) * deriv γ t) MeasureTheory.volume 0 1 := by
  have hcont : ContinuousOn (fun t => g (γ t) * derivWithin γ (Set.Icc 0 1) t)
      (Set.Icc 0 1) :=
    (hg.continuousOn.comp hγ.continuousOn hmaps).mul
      (hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl)
  have hint : IntervalIntegrable (fun t => g (γ t) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 :=
    hcont.intervalIntegrable_of_Icc (by norm_num : (0:ℝ) ≤ 1)
  apply hint.congr_ae
  apply (MeasureTheory.ae_restrict_iff' measurableSet_uIoc).mpr
  have hae_ne : ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ), t ≠ (1 : ℝ) :=
    MeasureTheory.measure_eq_zero_iff_ae_notMem.mp Real.volume_singleton
  filter_upwards [hae_ne] with t ht_ne ht_mem
  congr 1
  have htIoo : t ∈ Set.Ioo (0 : ℝ) 1 := by
    have hmem : t ∈ Set.Ioc (0 : ℝ) 1 := by
      rwa [← Set.uIoc_of_le (by norm_num : (0 : ℝ) ≤ 1)]
    exact ⟨hmem.1, lt_of_le_of_ne hmem.2 ht_ne⟩
  exact derivWithin_of_mem_nhds (Icc_mem_nhds htIoo.1 htIoo.2)



end Problems.residue_thm
