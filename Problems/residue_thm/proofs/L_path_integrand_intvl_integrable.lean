import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- path_integrand_intvl_integrable: IntervalIntegrable for P∘γ·γ' (P analytic off {a}, γ avoids a)
-- MapsTo from h_avoid; derivWithin continuity + a.e. congr switches deriv↔derivWithin.
theorem path_integrand_intvl_integrable
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    IntervalIntegrable (fun t => P (γ t) * deriv γ t) MeasureTheory.volume 0 1 := by
  have hmaps : Set.MapsTo γ (Set.Icc 0 1) (Set.univ \ {a}) := by
    intro t ht; simp [h_avoid t ht]
  have hcont : ContinuousOn (fun t => P (γ t) * derivWithin γ (Set.Icc 0 1) t) (Set.Icc 0 1) :=
    (hP.continuousOn.comp hγ.continuousOn hmaps).mul
      (hγ.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num)) le_rfl)
  have hint : IntervalIntegrable (fun t => P (γ t) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 := hcont.intervalIntegrable_of_Icc (by norm_num)
  apply hint.congr_ae
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
  refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
  filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
  simp [derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)]

end Problems.residue_thm

