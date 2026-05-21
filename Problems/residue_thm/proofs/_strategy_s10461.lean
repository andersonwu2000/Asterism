import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- Adapted from homotopy_integrand_intervalintegrable: build continuity of P a ∘ γ via
-- composition (γ avoids a since γ : Icc 0 1 → U \ T and a ∈ T), then use the
-- derivWithin trick (continuous derivWithin on Icc + congr_ae) to switch to deriv γ.
theorem s10461
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ)
    (hg : AnalyticOn ℂ g U)
    (hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (hpw : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    ∀ a ∈ T,
      IntervalIntegrable (fun t => P a (γ t) * deriv γ t)
        MeasureTheory.volume 0 1  := by
  intro a ha
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγ.continuousOn
  have hmaps' : Set.MapsTo γ (Set.Icc 0 1) (Set.univ \ {a}) := by
    intro t ht
    refine ⟨Set.mem_univ _, ?_⟩
    intro heq
    have hin : γ t ∈ U \ ↑T := hmaps ht
    exact hin.2 (heq ▸ ha)
  have hPaCont : ContinuousOn (P a) (Set.univ \ {a}) := (hPa a ha).continuousOn
  have hPaGammaCont : ContinuousOn (fun t => P a (γ t)) (Set.Icc (0:ℝ) 1) :=
    hPaCont.comp hγcont hmaps'
  have hdwcont : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc (0:ℝ) 1) :=
    hγ.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl
  have hprod : ContinuousOn (fun t => P a (γ t) * derivWithin γ (Set.Icc 0 1) t)
      (Set.Icc (0:ℝ) 1) := hPaGammaCont.mul hdwcont
  have hint : IntervalIntegrable (fun t => P a (γ t) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 :=
    hprod.intervalIntegrable_of_Icc (by norm_num : (0:ℝ) ≤ 1)
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
  exact derivWithin_of_mem_nhds (f := γ) (Icc_mem_nhds htIoo.1 htIoo.2)

end Problems.residue_thm
