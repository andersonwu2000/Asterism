import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- integrand_intvl_integrable_wrapper: IntervalIntegrable for g∘γ·γ' when g analytic on U
-- Downcasts AnalyticOn to ContinuousOn, then uses derivWithin continuity on Icc 0 1;
-- switches deriv to derivWithin a.e. on Ioo 0 1 (where Icc 0 1 ∈ nhds t).
theorem integrand_intvl_integrable_wrapper
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hg : AnalyticOn ℂ g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U) :
    IntervalIntegrable (fun t => g (γ t) * deriv γ t)
      MeasureTheory.volume 0 1 := by
  have hcont : ContinuousOn (fun t => g (γ t) * derivWithin γ (Set.Icc 0 1) t)
      (Set.Icc 0 1) :=
    (hg.continuousOn.comp hγ.continuousOn hmaps).mul
      (hγ.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num)) le_rfl)
  have hint : IntervalIntegrable (fun t => g (γ t) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 := hcont.intervalIntegrable_of_Icc (by norm_num)
  apply hint.congr_ae
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
  refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
  filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
  simp [derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)]

end Problems.residue_thm
