import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- path_int_integrand_interval_integrable: IntervalIntegrable for f(γ)·γ' using HasDerivAt→
-- DifferentiableOn→ContinuousOn f; derivWithin continuity on Icc a b; congr_ae on Ioo.
-- Case split a=b (trivially empty) vs a<b (use uniqueDiffOn_Icc + derivWithin=deriv a.e.).
theorem path_int_integrand_interval_integrable
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc a b))
    (hγU : Set.MapsTo γ (Set.Icc a b) (Metric.ball z₀ R)) :
    IntervalIntegrable (fun t => f (γ t) * deriv γ t)
      MeasureTheory.volume a b := by
  rcases eq_or_lt_of_le hab with rfl | hab_lt
  · constructor <;> simp [MeasureTheory.integrableOn_empty]
  · have hFdiff : DifferentiableOn ℂ F (Metric.ball z₀ R) :=
      fun z hz => (hF z hz).differentiableAt.differentiableWithinAt
    have hfcont : ContinuousOn f (Metric.ball z₀ R) := by
      have hderivF : DifferentiableOn ℂ (deriv F) (Metric.ball z₀ R) :=
        hFdiff.deriv Metric.isOpen_ball
      exact hderivF.continuousOn.congr (fun z hz => ((hF z hz).deriv).symm)
    have huniq : UniqueDiffOn ℝ (Set.Icc a b) := uniqueDiffOn_Icc hab_lt
    have hcont : ContinuousOn (fun t => f (γ t) * derivWithin γ (Set.Icc a b) t)
        (Set.Icc a b) :=
      (hfcont.comp hγ.continuousOn hγU).mul (hγ.continuousOn_derivWithin huniq le_rfl)
    have hint : IntervalIntegrable (fun t => f (γ t) * derivWithin γ (Set.Icc a b) t)
        MeasureTheory.volume a b :=
      hcont.intervalIntegrable_of_Icc hab
    apply hint.congr_ae
    rw [Set.uIoc_of_le hab]
    refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
    filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
    simp [derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)]
end Problems.residue_thm
