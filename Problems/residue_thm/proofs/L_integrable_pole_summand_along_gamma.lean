import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem integrable_pole_summand_along_gamma
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1) :
    ∀ a ∈ T, IntervalIntegrable
      (fun t => Complex.residue f a / (γ t - a) * deriv γ t)
      MeasureTheory.volume 0 1 := by
  intro a ha
  have hne : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t - a ≠ 0 := by
    intro t ht heq
    have hmem := hmap ht
    rw [Set.mem_diff] at hmem
    exact hmem.2 (Finset.mem_coe.mpr (sub_eq_zero.mp heq ▸ ha))
  have hcont_div : ContinuousOn (fun t => Complex.residue f a / (γ t - a)) (Set.Icc 0 1) :=
    ContinuousOn.div continuousOn_const
      (hγ.continuousOn.sub continuousOn_const)
      (fun t ht => hne t ht)
  have hcont_dw : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 1) :=
    hγ.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num : (0 : ℝ) < 1)) le_rfl
  have hvi : IntervalIntegrable
      (fun t => Complex.residue f a / (γ t - a) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 :=
    (hcont_div.mul hcont_dw).intervalIntegrable_of_Icc (by norm_num)
  refine hvi.congr_ae ?_
  rw [Set.uIoc_of_le (by norm_num : (0 : ℝ) ≤ 1)]
  rw [← MeasureTheory.restrict_Ioo_eq_restrict_Ioc]
  filter_upwards [MeasureTheory.self_mem_ae_restrict measurableSet_Ioo] with t ht
  congr 1
  exact derivWithin_of_mem_nhds
    (mem_nhds_iff.mpr ⟨Set.Ioo 0 1, Set.Ioo_subset_Icc_self, isOpen_Ioo, ht⟩)

end Problems.residue_thm
