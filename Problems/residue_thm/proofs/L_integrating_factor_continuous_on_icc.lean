import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- integrating_factor_continuous_on_icc: ContinuousOn of the integrating factor
-- (γ t - a)·exp(-∫₀ᵗ deriv γ s / (γ s - a)) on [0,1].
-- Strategy: show the integrand is IntervalIntegrable by comparing deriv γ to
-- derivWithin γ (Icc 0 1) (which is continuous from ContDiffOn 1) a.e. on Ioo 0 1,
-- then apply continuousOn_primitive_interval' and compose with exp.
theorem integrating_factor_continuous_on_icc
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (a : ℂ) (ha : a ∈ T) :
    ContinuousOn
      (fun t : ℝ => (γ t - a) * Complex.exp (- ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a)))
      (Set.Icc 0 1) := by
  have hne : ∀ t ∈ Set.Icc (0:ℝ) 1, γ t - a ≠ 0 := fun t ht =>
    sub_ne_zero.mpr fun h => (hmap ht).2 (h ▸ ha)
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have hdγ : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγ.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl
  have hint_cont : ContinuousOn (fun s => derivWithin γ (Set.Icc 0 1) s / (γ s - a))
      (Set.Icc 0 1) :=
    hdγ.div (hγcont.sub continuousOn_const) (fun s hs => hne s hs)
  have hint_intble : IntervalIntegrable (fun s => deriv γ s / (γ s - a))
      MeasureTheory.volume 0 1 := by
    apply (hint_cont.intervalIntegrable_of_Icc (by norm_num : (0:ℝ) ≤ 1)).congr_ae
    simp only [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
    rw [← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
    filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with s hs
    congr 1
    exact derivWithin_of_mem_nhds (Icc_mem_nhds hs.1 hs.2)
  have hprim : ContinuousOn
      (fun t => ∫ s in (0:ℝ)..t, deriv γ s / (γ s - a)) (Set.Icc 0 1) := by
    have h := intervalIntegral.continuousOn_primitive_interval' hint_intble
      (Set.left_mem_uIcc (a := (0:ℝ)) (b := 1))
    rwa [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1)] at h
  apply ContinuousOn.mul
  · exact hγcont.sub continuousOn_const
  · exact Complex.continuous_exp.comp_continuousOn hprim.neg

end Problems.residue_thm
