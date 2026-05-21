import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- residue_kernel_intvl_integrable: deriv γ / (γ - a) is interval-integrable on [0,1]
-- Uses derivWithin continuity on compact Icc, EqOn on interior Ioo, then
-- integrableOn_Icc_iff_integrableOn_Ioo (NoAtoms) + IntervalIntegrable via Ioc.
theorem residue_kernel_intvl_integrable
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    IntervalIntegrable (fun t => deriv γ t / (γ t - a)) MeasureTheory.volume 0 1 := by
  have huniq : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1) := uniqueDiffOn_Icc_zero_one
  -- derivWithin version is continuous, hence integrable on compact Icc 0 1
  have hcont : ContinuousOn (fun t => derivWithin γ (Set.Icc 0 1) t / (γ t - a)) (Set.Icc 0 1) :=
    (hγ.continuousOn_derivWithin huniq le_rfl).div
      (hγ.continuousOn.sub continuousOn_const)
      (fun t ht => sub_ne_zero.mpr (h_avoid t ht))
  have hint_dw : MeasureTheory.IntegrableOn
      (fun t => derivWithin γ (Set.Icc 0 1) t / (γ t - a))
      (Set.Icc 0 1) MeasureTheory.volume :=
    hcont.integrableOn_compact isCompact_Icc
  -- On Ioo 0 1, derivWithin = deriv (interior points have full nhds in Icc)
  have heq : Set.EqOn
      (fun t => derivWithin γ (Set.Icc 0 1) t / (γ t - a))
      (fun t => deriv γ t / (γ t - a))
      (Set.Ioo 0 1) := by
    intro t ht
    simp only
    congr 1
    exact hγ.differentiableOn_one t (Set.Ioo_subset_Icc_self ht)
      |>.differentiableAt (Icc_mem_nhds ht.1 ht.2)
      |>.derivWithin (huniq t (Set.Ioo_subset_Icc_self ht))
  have hint_Ioo : MeasureTheory.IntegrableOn (fun t => deriv γ t / (γ t - a))
      (Set.Ioo 0 1) MeasureTheory.volume :=
    ((integrableOn_Icc_iff_integrableOn_Ioo (a := (0:ℝ)) (b := 1)).mp hint_dw).congr_fun
      heq measurableSet_Ioo
  rw [intervalIntegrable_iff_integrableOn_Ioc_of_le zero_le_one]
  exact (integrableOn_Ioc_iff_integrableOn_Ioo (a := (0:ℝ)) (b := 1)).mpr hint_Ioo

end Problems.residue_thm
