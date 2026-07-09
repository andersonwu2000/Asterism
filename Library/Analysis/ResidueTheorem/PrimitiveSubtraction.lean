import Mathlib
import Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
import Library.Analysis.ResidueTheorem.PathIntegralFTC
import Library.Analysis.ResidueTheorem.PrimitiveConstruction
import Library.Analysis.ResidueTheorem.WindingCircleIntegral

/-!
# Primitive subtraction for the residue theorem

This file establishes the contour-integral identity
$$\int_0^1 P(\gamma t)\cdot\gamma'(t)\,dt
  = \operatorname{res}(P,a)\cdot\int_0^1 \frac{\gamma'(t)}{\gamma t - a}\,dt$$
for a function `P` analytic on `ℂ \ {a}` that decays at infinity, along a closed $C^1$
path `γ : [0,1] → ℂ` that avoids `a`.

The key technique is **primitive subtraction**: setting $Q := P - c/(z-a)$ with
$c := \operatorname{res}(P,a)$ produces a function with zero residue at `a`, so `Q`
admits a primitive on `ℂ \ {a}` via `primitive_punctured_of_decay_residue_zero`, and
the closed-loop integral of `Q` vanishes by the fundamental theorem of calculus.

## Main statements

* `subtracted_analytic_off_singularity`: `P z - c / (z - a)` is analytic on `ℂ \ {a}`.
* `subtracted_residue_zero`: the residue of `P z - c / (z - a)` at `a` is zero.
* `subtracted_tendsto_zero_cocompact`: cocompact decay is preserved under subtraction.
* `primitive_punctured_of_decay_residue_zero`: a zero-residue analytic function with
  cocompact decay admits a primitive on the punctured plane.
* `path_int_eq_residue_times_winding_int`: the path integral equals the residue times
  the winding integral.
-/

open Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
open Library.Analysis.ResidueTheorem.PathIntegralFTC
open Library.Analysis.ResidueTheorem.PrimitiveConstruction
open Library.Analysis.ResidueTheorem.WindingCircleIntegral

namespace Library.Analysis.ResidueTheorem.PrimitiveSubtraction

/-- If `P` is analytic on `ℂ \ {a}`, then `fun z => P z - Complex.residue P a / (z - a)`
is also analytic on `ℂ \ {a}`. -/
theorem subtracted_analytic_off_singularity
    {P : ℂ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a})) :
    AnalyticOn ℂ (fun z => P z - Complex.residue P a / (z - a))
      (Set.univ \ {a}) := by
  apply hP.sub
  apply AnalyticOn.div analyticOn_const (analyticOn_id.sub analyticOn_const)
  intro z hz
  simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and] at hz
  exact sub_ne_zero.mpr hz

/-- The residue of `fun z => P z - Complex.residue P a / (z - a)` at `a` is zero.

By linearity of circle integrals, `∮(P - c/(z-a)) = ∮P - c·2πi = 2πi·c - c·2πi = 0`,
using `residue_eq_circle_integral` for `P` and `integral_sub_center_inv` for `1/(z-a)`. -/
theorem subtracted_residue_zero
    {P : ℂ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a})) :
    Complex.residue (fun z => P z - Complex.residue P a / (z - a)) a = 0 := by
  set c := Complex.residue P a with hc_def
  have h2pi : (2 * (Real.pi : ℂ) * Complex.I) ≠ 0 := by
    have hpi : (Real.pi : ℂ) ≠ 0 := by exact_mod_cast Real.pi_ne_zero
    exact mul_ne_zero (mul_ne_zero (by norm_num) hpi) Complex.I_ne_zero
  -- Analyticity of P on ball a 1 \ {a}
  have hP1 : AnalyticOn ℂ P (Metric.ball a 1 \ {a}) :=
    hP.mono (Set.diff_subset_diff_left (Set.subset_univ _))
  -- Analyticity of (z - a)⁻¹ on ball a 1 \ {a}
  have hinv : AnalyticOn ℂ (fun z => (z - a)⁻¹) (Metric.ball a 1 \ {a}) :=
    (analyticOn_id.sub analyticOn_const).inv
      (fun z hz => sub_ne_zero.mpr (fun h => hz.2 (Set.mem_singleton_iff.mpr h)))
  -- Analyticity of c * (z - a)⁻¹ on ball a 1 \ {a}
  have hcinv : AnalyticOn ℂ (fun z => c * (z - a)⁻¹) (Metric.ball a 1 \ {a}) :=
    analyticOn_const.mul hinv
  -- Analyticity of Q on ball a 1 \ {a}
  have hQ : AnalyticOn ℂ (fun z => P z - c / (z - a)) (Metric.ball a 1 \ {a}) := by
    have : (fun z => P z - c / (z - a)) = (fun z => P z - c * (z - a)⁻¹) := by
      ext z; ring
    rw [this]
    exact hP1.sub hcinv
  -- Use residue_eq_circle_integral to express residue Q a via circle integral
  rw [show (fun z => P z - Complex.residue P a / (z - a)) =
        (fun z => P z - c / (z - a)) from rfl]
  rw [residue_eq_circle_integral hQ (by norm_num : (0:ℝ) < 1/2) (by norm_num : (1:ℝ)/2 < 1)]
  -- Helper: Metric.sphere a (1/2) ⊆ ball a 1 \ {a}
  have hsph_sub : Metric.sphere a (1/2) ⊆ Metric.ball a 1 \ {a} := by
    intro z hz
    rw [Metric.mem_sphere] at hz
    refine ⟨Metric.mem_ball.mpr (by linarith), ?_⟩
    intro h
    simp only [Set.mem_singleton_iff] at h
    rw [h, dist_self] at hz
    norm_num at hz
  -- CircleIntegrability
  have hP_ci : CircleIntegrable P a (1/2) := by
    apply ContinuousOn.circleIntegrable (by norm_num)
    exact hP.continuousOn.mono
      (hsph_sub.trans (Set.diff_subset_diff_left (Set.subset_univ _)))
  have hinv_ci : CircleIntegrable (fun z => (z - a)⁻¹) a (1/2) := by
    apply ContinuousOn.circleIntegrable (by norm_num)
    exact hinv.continuousOn.mono hsph_sub
  have hcinv_ci : CircleIntegrable (fun z => c / (z - a)) a (1/2) := by
    have : (fun z => c / (z - a)) = (fun z => c * (z - a)⁻¹) := by ext z; ring
    rw [this]
    exact hinv_ci.const_mul c
  -- Split by linearity, then compute each circle integral
  have hsplit : (∮ z in C(a, 1/2), (P z - c / (z - a))) =
      (∮ z in C(a, 1/2), P z) - ∮ z in C(a, 1/2), c / (z - a) :=
    circleIntegral.integral_sub hP_ci hcinv_ci
  have hcinv_int : (∮ z in C(a, 1/2), c / (z - a)) = c * (2 * Real.pi * Complex.I) := by
    have : (∮ z in C(a, 1/2), c / (z - a)) = c * ∮ z in C(a, 1/2), (z - a)⁻¹ := by
      simp_rw [div_eq_mul_inv]
      exact circleIntegral.integral_const_mul c (fun z => (z - a)⁻¹) a (1/2)
    rw [this, circleIntegral.integral_sub_center_inv a (by norm_num : (1:ℝ)/2 ≠ 0)]
  have hP_int : (∮ z in C(a, 1/2), P z) = 2 * Real.pi * Complex.I * c := by
    have heq := residue_eq_circle_integral hP1
        (by norm_num : (0:ℝ) < 1/2) (by norm_num : (1:ℝ)/2 < 1)
    rw [← hc_def] at heq
    field_simp [h2pi] at heq
    linear_combination -heq
  -- Combine: (1/(2πi)) * (2πi*c - c*2πi) = 0
  rw [hsplit, hcinv_int, hP_int]
  field_simp [h2pi]
  ring

/-- If `P` tends to zero along the cocompact filter on `ℂ`, then
`fun z => P z - Complex.residue P a / (z - a)` also tends to zero cocompactly,
since `(z - a)⁻¹ → 0` along cobounded sets. -/
theorem subtracted_tendsto_zero_cocompact
    {P : ℂ → ℂ} {a : ℂ}
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0)) :
    Filter.Tendsto (fun z => P z - Complex.residue P a / (z - a))
      (Filter.cocompact ℂ) (nhds 0) := by
  have h_inv : Filter.Tendsto (fun z : ℂ => (z - a)⁻¹) (Filter.cocompact ℂ) (nhds 0) := by
    rw [← Metric.cobounded_eq_cocompact]
    exact Filter.tendsto_inv₀_cobounded.comp (tendsto_sub_const_cobounded a)
  have h2 : Filter.Tendsto (fun z : ℂ => Complex.residue P a / (z - a))
      (Filter.cocompact ℂ) (nhds 0) := by
    simp_rw [div_eq_mul_inv]
    simpa using tendsto_const_nhds.mul h_inv
  simpa using hP_tendsto.sub h2

/-- Given a primitive `F` of `fun z => P z - Complex.residue P a / (z - a)` on `ℂ \ {a}`,
the contour integral of that function along a closed $C^1$ path `γ` in `ℂ \ {a}` vanishes
by the fundamental theorem of calculus: `∫ = F(γ 1) - F(γ 0) = 0`. -/
theorem closed_path_zero_from_punctured_primitive
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ} {F : ℂ → ℂ}
    (_hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1)
    (hF : ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (P z - Complex.residue P a / (z - a)) z) :
    (∫ t in (0:ℝ)..1, (P (γ t) - Complex.residue P a / (γ t - a)) * deriv γ t) = 0 := by
  have hU : IsOpen (Set.univ \ ({a} : Set ℂ)) := by
    rw [← Set.compl_eq_univ_diff]; exact isOpen_compl_singleton
  have hγU : Set.MapsTo γ (Set.Icc 0 1) (Set.univ \ ({a} : Set ℂ)) := fun t ht =>
    ⟨Set.mem_univ _, h_avoid t ht⟩
  have hftc := path_integral_eq_primitive_diff hU hF hγ hγU
  rw [hftc, ← hclosed, sub_self]

/-- An analytic function `Q` on `ℂ \ {a}` with `Complex.residue Q a = 0` that tends to
zero cocompactly admits a primitive on `ℂ \ {a}`.

The proof uses `analytic_residue_zero_decay_closed_loop_zero` (all closed loops integrate
to zero under these hypotheses) together with `primitive_on_punctured_plane_from_zero_loops`
(a Morera-style primitive construction from the vanishing-loop hypothesis). -/
theorem primitive_punctured_of_decay_residue_zero
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    (hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0))
    (hQ_res : Complex.residue Q a = 0) :
    ∃ F : ℂ → ℂ, ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (Q z) z := by
  have h_loops :
      ∀ γ : ℝ → ℂ, ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
        (∀ t ∈ Set.Icc (0:ℝ) 1, γ t ≠ a) → γ 0 = γ 1 →
        (∫ t in (0:ℝ)..1, Q (γ t) * deriv γ t) = 0 := fun γ hγ h_avoid hclosed =>
    analytic_residue_zero_decay_closed_loop_zero hQ_an hQ_decay hQ_res γ hγ h_avoid hclosed
  exact primitive_on_punctured_plane_from_zero_loops hQ_an h_loops

/-- A primitive of `fun z => P z - Complex.residue P a / (z - a)` exists on `ℂ \ {a}`.

Sets `Q := P - r/(· - a)` (where `r := Complex.residue P a`); then `Q` is analytic on
`ℂ \ {a}` by `subtracted_analytic_off_singularity`, decays at infinity by
`subtracted_tendsto_zero_cocompact`, and has zero residue by `subtracted_residue_zero`,
so `primitive_punctured_of_decay_residue_zero` yields the desired primitive. -/
theorem punctured_primitive_subtracted
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (_hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (_h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (_hclosed : γ 0 = γ 1) :
    ∃ F : ℂ → ℂ, ∀ z ∈ Set.univ \ ({a} : Set ℂ),
      HasDerivAt F (P z - Complex.residue P a / (z - a)) z := by
  set r : ℂ := Complex.residue P a with hr_def
  set Q : ℂ → ℂ := fun z => P z - r / (z - a) with hQdef
  have hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}) :=
    subtracted_analytic_off_singularity (P := P) (a := a) hP
  have hQ_decay : Filter.Tendsto Q (Filter.cocompact ℂ) (nhds 0) :=
    subtracted_tendsto_zero_cocompact (P := P) (a := a) hP_tendsto
  have hQ_res : Complex.residue Q a = 0 :=
    subtracted_residue_zero (P := P) (a := a) hP
  obtain ⟨F, hF⟩ :=
    primitive_punctured_of_decay_residue_zero (Q := Q) (a := a) hQ_an hQ_decay hQ_res
  refine ⟨F, ?_⟩
  intro z hz
  simpa [hQdef, hr_def] using hF z hz

/-- `t ↦ P(γ t) * deriv γ t` is interval-integrable on `[0, 1]` when `P` is analytic on
`ℂ \ {a}` and `γ` is a $C^1$ path avoiding `a`.

The integrand is continuous via `derivWithin` on `Set.Icc 0 1`; an almost-everywhere
equality on `Set.Ioo 0 1` converts `derivWithin` to `deriv`. -/
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

/-- `t ↦ deriv γ t / (γ t - a)` is interval-integrable on `[0, 1]` when `γ` is a
$C^1$ path avoiding `a`.

Uses `derivWithin` continuity on the compact `Set.Icc 0 1`, an `EqOn` equality on the
interior `Set.Ioo 0 1`, and the equivalence between integrability on `Icc`, `Ioo`, and
`Ioc`. -/
theorem residue_kernel_intvl_integrable
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    IntervalIntegrable (fun t => deriv γ t / (γ t - a)) MeasureTheory.volume 0 1 := by
  have huniq : UniqueDiffOn ℝ (Set.Icc (0:ℝ) 1) := uniqueDiffOn_Icc_zero_one
  -- derivWithin version is continuous, hence integrable on compact Icc 0 1
  have hcont :
      ContinuousOn (fun t => derivWithin γ (Set.Icc 0 1) t / (γ t - a)) (Set.Icc 0 1) :=
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

/-- The contour integral of `(P(γ t) - r/(γ t - a)) * deriv γ t` equals the difference of
the `P`-integral and `r` times the winding integral, where `r := Complex.residue P a`:
$$\int_0^1 \bigl(P(\gamma t) - r/(\gamma t-a)\bigr)\gamma'(t)\,dt
  = \int_0^1 P(\gamma t)\,\gamma'(t)\,dt
    - r\cdot\int_0^1 \tfrac{\gamma'(t)}{\gamma t - a}\,dt.$$
This follows from interval-integral linearity once both summands are shown integrable via
`path_integrand_intvl_integrable` and `residue_kernel_intvl_integrable`. -/
theorem path_int_split_residue_term
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (_hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (_hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, (P (γ t) - Complex.residue P a / (γ t - a)) * deriv γ t) =
      (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) -
        Complex.residue P a * (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) := by
  set r := Complex.residue P a with hr_def
  have hA : IntervalIntegrable (fun t => P (γ t) * deriv γ t) MeasureTheory.volume 0 1 :=
    path_integrand_intvl_integrable hP hγ h_avoid
  have hB : IntervalIntegrable (fun t => deriv γ t / (γ t - a)) MeasureTheory.volume 0 1 :=
    residue_kernel_intvl_integrable hγ h_avoid
  have hB' : IntervalIntegrable (fun t => r * (deriv γ t / (γ t - a))) MeasureTheory.volume 0 1 :=
    hB.const_mul r
  have heq : ∀ t ∈ Set.uIcc (0:ℝ) 1,
      (P (γ t) - r / (γ t - a)) * deriv γ t =
      P (γ t) * deriv γ t - r * (deriv γ t / (γ t - a)) := by
    intro t _; ring
  rw [intervalIntegral.integral_congr heq]
  rw [intervalIntegral.integral_sub hA hB']
  congr 1
  exact intervalIntegral.integral_const_mul r (fun t => deriv γ t / (γ t - a))

/-- The contour integral `∫₀¹ (P(γ t) - r/(γ t - a)) * deriv γ t dt` vanishes for a
closed $C^1$ path `γ` in `ℂ \ {a}`, where `r := Complex.residue P a`.

The subtracted function `Q := P - r/(· - a)` admits a primitive `F` on `ℂ \ {a}` by
`punctured_primitive_subtracted`, and the closed-loop integral collapses to
`F(γ 1) - F(γ 0) = 0` by `closed_path_zero_from_punctured_primitive`. -/
theorem residue_subtracted_path_int_zero
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, (P (γ t) - Complex.residue P a / (γ t - a)) * deriv γ t) = 0 := by
  have h_prim :=
    punctured_primitive_subtracted hP hP_tendsto hγ h_avoid hclosed
  obtain ⟨F, hF⟩ := h_prim
  exact closed_path_zero_from_punctured_primitive
    (F := F) hP hP_tendsto hγ h_avoid hclosed hF

/-- **Path integral equals residue times winding integral**: for `P` analytic on `ℂ \ {a}`
and decaying at infinity, and a closed $C^1$ path `γ` in `ℂ \ {a}`,
$$\int_0^1 P(\gamma t)\cdot\gamma'(t)\,dt
  = \operatorname{res}(P,a)\cdot\int_0^1 \frac{\gamma'(t)}{\gamma t - a}\,dt.$$
The proof subtracts `r/(z - a)` (with `r := Complex.residue P a`) to land in the
zero-residue regime where the closed-loop integral vanishes (`residue_subtracted_path_int_zero`),
then recovers the identity via `path_int_split_residue_term`. -/
theorem path_int_eq_residue_times_winding_int
    {P : ℂ → ℂ} {γ : ℝ → ℂ} {a : ℂ}
    (hP : AnalyticOn ℂ P (Set.univ \ {a}))
    (hP_tendsto : Filter.Tendsto P (Filter.cocompact ℂ) (nhds 0))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (h_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a)
    (hclosed : γ 0 = γ 1) :
    (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t)
      = Complex.residue P a * (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) := by
  have hA := residue_subtracted_path_int_zero hP hP_tendsto hγ h_avoid hclosed
  have hB := path_int_split_residue_term hP hP_tendsto hγ h_avoid hclosed
  have h_sub_zero : (∫ t in (0:ℝ)..1, P (γ t) * deriv γ t) -
      Complex.residue P a * (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 0 := by
    rw [← hB]; exact hA
  exact sub_eq_zero.mp h_sub_zero

end Library.Analysis.ResidueTheorem.PrimitiveSubtraction
