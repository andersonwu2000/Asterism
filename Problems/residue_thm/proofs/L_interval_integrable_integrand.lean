import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- interval_integrable_integrand: IntervalIntegrable via holomorphicity of f (HasDerivAt →
-- DifferentiableOn → AnalyticOn → continuous deriv F = f) + ContinuousOn.intervalIntegrable_of_Icc
-- on the derivWithin version, then congr_ae (deriv = derivWithin a.e. on Ioc 0 1 \ {1}).
-- entry_kind: Builder
theorem interval_integrable_integrand
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    IntervalIntegrable (fun t => f (γ t) * deriv γ t) MeasureTheory.volume 0 1 := by
  have hFdiff : DifferentiableOn ℂ F U :=
    fun z hz => (hF z hz).differentiableAt.differentiableWithinAt
  have hfcont : ContinuousOn f U := by
    have hderivF : DifferentiableOn ℂ (deriv F) U := hFdiff.deriv hU
    exact hderivF.continuousOn.congr (fun z hz => ((hF z hz).deriv).symm)
  have hfγcont : ContinuousOn (fun t => f (γ t)) (Set.Icc 0 1) :=
    hfcont.comp hγC1.continuousOn hγU
  have hdwcont : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγC1.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hprod : ContinuousOn (fun t => f (γ t) * derivWithin γ (Set.Icc 0 1) t) (Set.Icc 0 1) :=
    hfγcont.mul hdwcont
  have hint : IntervalIntegrable (fun t => f (γ t) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 := hprod.intervalIntegrable_of_Icc (by norm_num : (0:ℝ) ≤ 1)
  apply hint.congr_ae
  apply (MeasureTheory.ae_restrict_iff' measurableSet_uIoc).mpr
  have hae_ne : ∀ᵐ t ∂(MeasureTheory.volume : MeasureTheory.Measure ℝ), t ≠ (1:ℝ) :=
    MeasureTheory.measure_eq_zero_iff_ae_notMem.mp Real.volume_singleton
  filter_upwards [hae_ne] with t ht_ne ht_mem
  congr 1
  have htIoo : t ∈ Set.Ioo (0:ℝ) 1 := by
    have hmem : t ∈ Set.Ioc (0:ℝ) 1 := by
      rwa [← Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
    exact ⟨hmem.1, lt_of_le_of_ne hmem.2 ht_ne⟩
  exact derivWithin_of_mem_nhds (Icc_mem_nhds htIoo.1 htIoo.2)

end Problems.residue_thm