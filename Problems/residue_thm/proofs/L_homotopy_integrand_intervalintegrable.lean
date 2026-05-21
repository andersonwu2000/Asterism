import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- homotopy_integrand_intervalintegrable: ContinuousOn + derivWithin slice from C² product,
-- then congr_ae (deriv = derivWithin on Ioo 0 1 a.e.) closes IntervalIntegrable goal.
theorem homotopy_integrand_intervalintegrable
    {V : Set ℂ} {f : ℂ → ℂ} {H : ℝ → ℝ → ℂ}
    (hV : IsOpen V)
    (hf : AnalyticOn ℂ f V)
    (hH : ContDiffOn ℝ 2 (fun p : ℝ × ℝ => H p.1 p.2)
            (Set.Icc (0:ℝ) 1 ×ˢ Set.Icc (0:ℝ) 1))
    (hHV : ∀ τ ∈ Set.Icc (0:ℝ) 1, ∀ t ∈ Set.Icc (0:ℝ) 1, H τ t ∈ V)
    (hH0 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 0 = H 0 0)
    (hH1 : ∀ τ ∈ Set.Icc (0:ℝ) 1, H τ 1 = H 0 1) :
    ∀ τ ∈ Set.Icc (0:ℝ) 1,
      IntervalIntegrable (fun t => f (H τ t) * deriv (H τ) t)
        MeasureTheory.volume 0 1 := by
  intro τ hτ
  have hslice1 : ContDiffOn ℝ 1 (H τ) (Set.Icc (0:ℝ) 1) := by
    have hH1 : ContDiffOn ℝ 1 (fun p : ℝ × ℝ => H p.1 p.2) (Set.Icc 0 1 ×ˢ Set.Icc 0 1) :=
      hH.of_le (by norm_num)
    have hpair : ContDiffOn ℝ 1 (fun t : ℝ => (τ, t)) (Set.Icc (0:ℝ) 1) :=
      (contDiff_prodMk_right τ).contDiffOn
    exact hH1.comp hpair (fun t ht => ⟨hτ, ht⟩)
  have hfHcont : ContinuousOn (fun t => f (H τ t)) (Set.Icc (0:ℝ) 1) :=
    hf.continuousOn.comp hslice1.continuousOn (fun t ht => hHV τ hτ t ht)
  have hdwcont : ContinuousOn (derivWithin (H τ) (Set.Icc 0 1)) (Set.Icc (0:ℝ) 1) :=
    hslice1.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hprod : ContinuousOn (fun t => f (H τ t) * derivWithin (H τ) (Set.Icc 0 1) t)
      (Set.Icc (0:ℝ) 1) := hfHcont.mul hdwcont
  have hint : IntervalIntegrable (fun t => f (H τ t) * derivWithin (H τ) (Set.Icc 0 1) t)
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
