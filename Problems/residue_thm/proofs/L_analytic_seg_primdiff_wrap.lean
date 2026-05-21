import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- analytic_seg_primdiff_wrap: DifferentiableOn.isExactOn_ball (Mathlib) yields F;
-- FTC via integral_eq_sub_of_hasDerivAt_of_le with chain-rule interior deriv + continuity.
theorem analytic_seg_primdiff_wrap
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ' : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hf : DifferentiableOn ℂ f (Metric.ball z₀ R))
    (hγ : ContDiffOn ℝ 1 γ' (Set.Icc a b))
    (hγU : Set.MapsTo γ' (Set.Icc a b) (Metric.ball z₀ R)) :
    ∃ F : ℂ → ℂ,
      (∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z) ∧
      (∫ t in a..b, f (γ' t) * deriv γ' t) = F (γ' b) - F (γ' a) := by
  obtain ⟨F, hF⟩ := hf.isExactOn_ball
  refine ⟨F, hF, ?_⟩
  have h_cont : ContinuousOn (fun t => F (γ' t)) (Set.Icc a b) := by
    have hFcont : ContinuousOn F (Metric.ball z₀ R) :=
      fun z hz => (hF z hz).continuousAt.continuousWithinAt
    exact hFcont.comp hγ.continuousOn hγU
  have h_deriv : ∀ x ∈ Set.Ioo a b,
      HasDerivAt (fun s => F (γ' s)) (f (γ' x) * deriv γ' x) x := by
    intro x hx
    have hx_mem : x ∈ Set.Icc a b := Set.mem_Icc_of_Ioo hx
    have hFγx : HasDerivAt F (f (γ' x)) (γ' x) := hF (γ' x) (hγU hx_mem)
    have hIcc_nhds : Set.Icc a b ∈ nhds x := Icc_mem_nhds hx.1 hx.2
    have hγDA : DifferentiableAt ℝ γ' x :=
      (hγ.differentiableOn one_ne_zero x hx_mem).differentiableAt hIcc_nhds
    exact hFγx.comp x hγDA.hasDerivAt
  have h_int : IntervalIntegrable (fun t => f (γ' t) * deriv γ' t)
      MeasureTheory.volume a b := by
    rcases eq_or_lt_of_le hab with rfl | hab_lt
    · constructor <;> simp [MeasureTheory.integrableOn_empty]
    · have hfcont : ContinuousOn f (Metric.ball z₀ R) := hf.continuousOn
      have huniq : UniqueDiffOn ℝ (Set.Icc a b) := uniqueDiffOn_Icc hab_lt
      have hcont : ContinuousOn (fun t => f (γ' t) * derivWithin γ' (Set.Icc a b) t)
          (Set.Icc a b) :=
        (hfcont.comp hγ.continuousOn hγU).mul (hγ.continuousOn_derivWithin huniq le_rfl)
      apply (hcont.intervalIntegrable_of_Icc hab).congr_ae
      rw [Set.uIoc_of_le hab]
      refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict
        MeasureTheory.Ioo_ae_eq_Ioc ?_
      filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
      simp [derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)]
  exact intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le hab h_cont h_deriv h_int

end Problems.residue_thm
