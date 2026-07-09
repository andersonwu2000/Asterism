import Mathlib
import Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
import Library.Analysis.ResidueTheorem.GlobalRemainder

/-!
# Path integral decomposition for meromorphic functions

This file provides tools for decomposing the path integral of a meromorphic function
`f : ℂ → ℂ` along a $C^1$ path `γ : [0,1] → U \setminus T$ into a sum of integrals of
an analytic remainder `g` and principal parts `P a` for each pole `a ∈ T`.

## Main statements

- `pointwise_integrand_decomp`: the integrand `f(γ(t)) · γ'(t)` equals
  `g(γ(t)) · γ'(t) + ∑ a, P a (γ(t)) · γ'(t)` pointwise on `[0,1]`.
- `principal_along_path_intvl_integrable`: each principal-part integrand
  `P a ∘ γ · γ'` is interval-integrable on `[0,1]`.
- `intvl_integrable_continuous_circ_c1`: a continuous function composed with a $C^1$
  path gives an interval-integrable integrand.
- `g_along_path_intvl_integrable`: the analytic remainder integrand `g ∘ γ · γ'` is
  interval-integrable on `[0,1]`.
- `integral_decomp_from_pointwise`: the path integral of `f` decomposes as the sum of
  the path integral of `g` and the path integrals of the principal parts.
- `analytic_remainder_principal_part_decomp`: existence of an analytic remainder `g` and
  principal parts `P` realizing the full integral decomposition, with the residues of `P a`
  matching those of `f` at each pole `a ∈ T`.
-/

open Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
open Library.Analysis.ResidueTheorem.GlobalRemainder

namespace Library.Analysis.ResidueTheorem.PathIntegralDecomp

/-- The integrand of `f` along `γ` decomposes pointwise as the integrand of the analytic
remainder `g` plus the sum of the principal-part integrands. That is, for all `t ∈ [0,1]`,
`f(γ(t)) · γ'(t) = g(γ(t)) · γ'(t) + ∑ a ∈ T, P a (γ(t)) · γ'(t)`. -/
theorem pointwise_integrand_decomp
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (_hf : AnalyticOn ℂ f (U \ ↑T))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ)
    (_hg : AnalyticOn ℂ g U)
    (_hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (hpw : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    ∀ t ∈ Set.Icc (0:ℝ) 1,
      f (γ t) * deriv γ t =
        g (γ t) * deriv γ t + ∑ a ∈ T, P a (γ t) * deriv γ t := by
  intro t ht
  have heq := hpw (γ t) (hmaps ht)
  rw [heq, add_mul, Finset.sum_mul]

/-- Each principal-part integrand `P a ∘ γ · γ'` is interval-integrable on `[0,1]`.
Since `γ` maps into `U \ T`, we have `γ(t) ≠ a` for all `a ∈ T`, so `P a ∘ γ` is
continuous; the derivative `γ'` is handled via `derivWithin` on `Set.Icc 0 1` and
an almost-everywhere congr argument. -/
theorem principal_along_path_intvl_integrable
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (_hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ)
    (_hg : AnalyticOn ℂ g U)
    (hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (_hpw : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    ∀ a ∈ T,
      IntervalIntegrable (fun t => P a (γ t) * deriv γ t)
        MeasureTheory.volume 0 1 := by
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

/-- If `g` is continuous on `U` and `γ : [0,1] → U` is a $C^1$ path, then the integrand
`g(γ(t)) · γ'(t)` is interval-integrable on `[0,1]`. -/
theorem intvl_integrable_continuous_circ_c1
    {U : Set ℂ} {g : ℂ → ℂ} {γ : ℝ → ℂ}
    (hg : ContinuousOn g U)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) U) :
    IntervalIntegrable (fun t => g (γ t) * deriv γ t)
      MeasureTheory.volume 0 1 := by
  have hcont : ContinuousOn (fun t => g (γ t) * derivWithin γ (Set.Icc 0 1) t) (Set.Icc 0 1) :=
    (hg.comp hγ.continuousOn hmaps).mul
      (hγ.continuousOn_derivWithin (uniqueDiffOn_Icc (by norm_num)) le_rfl)
  have hint : IntervalIntegrable (fun t => g (γ t) * derivWithin γ (Set.Icc 0 1) t)
      MeasureTheory.volume 0 1 := hcont.intervalIntegrable_of_Icc (by norm_num)
  apply hint.congr_ae
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1)]
  refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
  filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
  simp [derivWithin_of_mem_nhds (Icc_mem_nhds ht.1 ht.2)]

/-- The analytic-remainder integrand `g(γ(t)) · γ'(t)` is interval-integrable on `[0,1]`.
This follows from `intvl_integrable_continuous_circ_c1` applied to `hg.continuousOn`. -/
theorem g_along_path_intvl_integrable
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (_hU : IsOpen U)
    (_hT : ∀ a ∈ T, a ∈ U)
    (_hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ)
    (hg : AnalyticOn ℂ g U)
    (_hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}))
    (_hpw : ∀ z ∈ U \ ↑T, f z = g z + ∑ a ∈ T, P a z) :
    IntervalIntegrable (fun t => g (γ t) * deriv γ t) MeasureTheory.volume 0 1 :=
  intvl_integrable_continuous_circ_c1 hg.continuousOn hγ (hmaps.mono_right Set.diff_subset)

/-- The path integral of `f` decomposes as the path integral of the analytic remainder `g`
plus the sum of the path integrals of the principal parts `P a`. Concretely,
`∫ t in 0..1, f(γ(t)) · γ'(t) = ∫ t in 0..1, g(γ(t)) · γ'(t) +
  ∑ a ∈ T, ∫ t in 0..1, P a (γ(t)) · γ'(t)`.
The proof uses `intervalIntegral.integral_congr` to substitute the pointwise decomposition,
`intervalIntegral.integral_add` to split the sum, and `intervalIntegral.integral_finsetSum`
to push `∑ a ∈ T` outside the integral. -/
theorem integral_decomp_from_pointwise
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
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
      (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) +
      ∑ a ∈ T, ∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t := by
  have h_pw_Icc :=
    pointwise_integrand_decomp hU hT hf hγ hmaps g P hg hPa hpw
  have h_g_int :=
    g_along_path_intvl_integrable hU hT hf hγ hmaps g P hg hPa hpw
  have h_P_int :=
    principal_along_path_intvl_integrable hU hT hf hγ hmaps g P hg hPa hpw
  have h_sum_int : IntervalIntegrable (fun t => ∑ a ∈ T, P a (γ t) * deriv γ t)
                    MeasureTheory.volume 0 1 := by
    have hsum := IntervalIntegrable.sum (μ := MeasureTheory.volume) (a := (0:ℝ)) (b := 1)
              T (f := fun a t => P a (γ t) * deriv γ t)
              (fun a ha => h_P_int a ha)
    convert hsum using 1
    funext t
    simp [Finset.sum_apply]
  have h_pw_uIcc : Set.EqOn (fun t => f (γ t) * deriv γ t)
                            (fun t => g (γ t) * deriv γ t + ∑ a ∈ T, P a (γ t) * deriv γ t)
                            (Set.uIcc (0:ℝ) 1) := by
    rw [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1)]
    intro t ht
    exact h_pw_Icc t ht
  rw [intervalIntegral.integral_congr h_pw_uIcc,
      intervalIntegral.integral_add h_g_int h_sum_int,
      intervalIntegral.integral_finsetSum (fun a ha => h_P_int a ha)]

/-- **Analytic remainder and principal-part decomposition**: given a meromorphic function
`f` analytic on `U \ T` and a $C^1$ path `γ : [0,1] → U \setminus T$, there exist an
analytic function `g` on `U` and principal parts `P : ℂ → ℂ → ℂ` such that:
- `g` is analytic on `U`;
- each `P a` is analytic on `Set.univ \ {a}` and tends to `0` at cocompact infinity;
- the residue of `P a` at `a` equals the residue of `f` at `a` for each `a ∈ T`;
- the path integral decomposes as `∫ t in 0..1, f(γ(t)) · γ'(t) =
  ∫ t in 0..1, g(γ(t)) · γ'(t) + ∑ a ∈ T, ∫ t in 0..1, P a (γ(t)) · γ'(t)`. -/
theorem analytic_remainder_principal_part_decomp
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ (g : ℂ → ℂ) (P : ℂ → ℂ → ℂ),
      AnalyticOn ℂ g U ∧
      (∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a})) ∧
      (∀ a ∈ T, Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0)) ∧
      (∀ a ∈ T, Complex.residue (P a) a = Complex.residue f a) ∧
      (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
        (∫ t in (0:ℝ)..1, g (γ t) * deriv γ t) +
        ∑ a ∈ T, ∫ t in (0:ℝ)..1, P a (γ t) * deriv γ t := by
  have h_per := per_pole_principal_part_data hU hT hf hγ hmaps
  obtain ⟨P, R, h, hper⟩ := h_per
  have h_glue := global_remainder_glue hU hT hf hγ hmaps P R h hper
  obtain ⟨g, hg, hpw, hres⟩ := h_glue
  have hPa : ∀ a ∈ T, AnalyticOn ℂ (P a) (Set.univ \ {a}) :=
    fun a ha => (hper a ha).2.2.2.1
  have hPt : ∀ a ∈ T, Filter.Tendsto (P a) (Filter.cocompact ℂ) (nhds 0) :=
    fun a ha => (hper a ha).2.2.2.2.1
  have h_int := integral_decomp_from_pointwise hU hT hf hγ hmaps g P hg hPa hpw
  exact ⟨g, P, hg, hPa, hPt, hres, h_int⟩

end Library.Analysis.ResidueTheorem.PathIntegralDecomp
