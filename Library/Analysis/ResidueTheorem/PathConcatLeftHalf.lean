import Mathlib.Analysis.Calculus.Deriv.Mul
import Mathlib.MeasureTheory.Integral.IntervalIntegral.ContDiff
import Library.Analysis.ResidueTheorem.PathConcatSmoothness

/-!
# Left-half integrals for path concatenation

This file proves the integral identities needed for the left half `[0, 1/2]` when
computing the contour integral along a concatenated path `α' ++ β'`.

## Main statements

- `concat_velocity_if_eq_left_on_prefix`: the piecewise velocity integrand collapses to the
  `α'`-branch on `[0, t]` when `t ∈ [0, 1/2]`.
- `integral_two_deriv_within_double_eq_diff`: FTC with the linear substitution `u = 2s` gives
  `∫₀ᵗ 2·derivWithin α'(2s) ds = α'(2t) - α'(0)` for a $C^1$ path `α'`.
- `flat_concat_ftc_left_half`: on the left half, the accumulated piecewise integral equals
  `α'(2t)`.
- `flat_ftc_left_half_int_eq`: the contour integral over `[0, 1/2]` of `Q(γ)·γ'` equals
  the contour integral of `Q(α')·α'` over `[0, 1]`.
-/

open Library.Analysis.ResidueTheorem.PathConcatSmoothness

namespace Library.Analysis.ResidueTheorem.PathConcatLeftHalf

/-- On the interval `[0, t]` with `t ∈ [0, 1/2]`, the piecewise velocity integrand
equals the `α'`-branch `2 * derivWithin α' (Set.Icc 0 1) (2 * s)`. -/
theorem concat_velocity_if_eq_left_on_prefix
    {α' β' : ℝ → ℂ}
    {t : ℝ} (ht : t ∈ Set.Icc (0 : ℝ) (1 / 2)) :
    (∫ s in (0 : ℝ)..t,
        (if s ≤ (1 : ℝ) / 2
          then 2 * derivWithin α' (Set.Icc 0 1) (2 * s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2 * s - 1))) =
    (∫ s in (0 : ℝ)..t, 2 * derivWithin α' (Set.Icc 0 1) (2 * s)) := by
  apply intervalIntegral.integral_congr
  intro s hs
  simp only [Set.uIcc_of_le ht.1] at hs
  have hs_le : s ≤ 1 / 2 := le_trans hs.2 ht.2
  simp only [if_pos hs_le]

/-- FTC with the linear substitution `u = 2s`: for a $C^1$ path `α'` on `[0, 1]` and
`t ∈ [0, 1/2]`, we have `∫₀ᵗ 2 * derivWithin α' (Icc 0 1) (2s) ds = α'(2t) - α'(0)`. -/
theorem integral_two_deriv_within_double_eq_diff
    {α' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    {t : ℝ} (ht : t ∈ Set.Icc (0 : ℝ) (1 / 2)) :
    (∫ s in (0 : ℝ)..t, 2 * derivWithin α' (Set.Icc 0 1) (2 * s)) =
        α' (2 * t) - α' 0 := by
  have ht0 : (0 : ℝ) ≤ t := ht.1
  have ht2 : t ≤ 1 / 2 := ht.2
  have key : ∫ s in (0:ℝ)..t, 2 * derivWithin α' (Set.Icc 0 1) (2 * s) =
      (fun s => α' (2 * s)) t - (fun s => α' (2 * s)) 0 := by
    apply intervalIntegral.integral_eq_sub_of_hasDerivAt_of_le ht0
    · have hf : ContinuousOn (fun s : ℝ => 2 * s) (Set.Icc 0 t) :=
        (continuous_const.mul continuous_id').continuousOn.mono (Set.subset_univ _)
      refine ContinuousOn.comp hα'.continuousOn hf ?_
      intro s hs
      simp only [Set.mem_Icc] at hs ⊢
      exact ⟨by linarith, by linarith⟩
    · intro s hs
      have h2s_pos : (0 : ℝ) < 2 * s := by linarith [hs.1]
      have h2s_lt1 : 2 * s < 1 := by linarith [hs.2]
      have hIcc_nhds : Set.Icc 0 1 ∈ nhds (2 * s) := Icc_mem_nhds h2s_pos h2s_lt1
      have hDiff : DifferentiableAt ℝ α' (2 * s) :=
        (hα'.differentiableOn one_ne_zero (2 * s) (Set.mem_Icc.mpr
          ⟨le_of_lt h2s_pos, le_of_lt h2s_lt1⟩)).differentiableAt hIcc_nhds
      have hderiv_eq : derivWithin α' (Set.Icc 0 1) (2 * s) = deriv α' (2 * s) :=
        hDiff.derivWithin (uniqueDiffWithinAt_of_mem_nhds hIcc_nhds)
      rw [hderiv_eq]
      have h_lin : HasDerivAt (fun s => 2 * s) 2 s := by
        simpa using (hasDerivAt_id s).const_mul 2
      have h_comp := hDiff.hasDerivAt.scomp s h_lin
      convert h_comp using 1
    · apply ContinuousOn.intervalIntegrable_of_Icc ht0
      apply ContinuousOn.mul continuousOn_const
      have hf : ContinuousOn (fun s : ℝ => 2 * s) (Set.Icc 0 t) :=
        (continuous_const.mul continuous_id').continuousOn.mono (Set.subset_univ _)
      refine ContinuousOn.comp (hα'.continuousOn_derivWithin
        (uniqueDiffOn_Icc (by norm_num : (0:ℝ) < 1)) le_rfl) hf ?_
      intro s hs
      simp only [Set.mem_Icc] at hs ⊢
      exact ⟨by linarith, by linarith⟩
  simp only [mul_zero, key]

/-- For any `t ∈ [0, 1/2]`, the piecewise-integral primitive satisfies
`α'(0) + ∫₀ᵗ v(s) ds = α'(2t)`, where `v` is the concatenated velocity.
Proved by collapsing the `if`-branch to the `α'`-branch and then applying FTC
with the substitution `u = 2s`. -/
theorem flat_concat_ftc_left_half
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_h_match : α' 1 = β' 0)
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc (0:ℝ) (1/2),
      α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = α' (2*t) := by
  intro t ht
  have h_int_simp := concat_velocity_if_eq_left_on_prefix (α' := α') (β' := β') ht
  have h_ftc := integral_two_deriv_within_double_eq_diff hα' ht
  rw [h_int_simp, h_ftc]; ring

/-- Variant of `flat_concat_ftc_left_half` carrying the full analytic data of the
concatenation. For `t ∈ [0, 1/2]` the piecewise-integral primitive equals `α'(2t)`. -/
theorem flat_left_h_eq_alpha
    {Q : ℂ → ℂ} {a : ℂ}
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc (0:ℝ) (1/2),
      α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) = α' (2*t) :=
    flat_concat_ftc_left_half hα' hβ' h_match hα'_deriv hβ'_deriv

/-- The piecewise integral over `[0, 1/2]` with concatenated velocity equals `α'(1) - α'(0)`,
computed via change of variables `u = 2s` and the FTC for `α'`. -/
theorem flat_concat_left_half_piecewise_eval
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_h_match : α' 1 = β' 0)
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    (∫ s in (0:ℝ)..((1:ℝ)/2),
      (if s ≤ (1:ℝ)/2
        then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
      = α' 1 - α' 0 := by
  have h1 : ∫ s in (0:ℝ)..(1/2),
      (if s ≤ (1:ℝ)/2 then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
       else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) =
    ∫ s in (0:ℝ)..(1/2), 2 * derivWithin α' (Set.Icc 0 1) (2*s) := by
    apply intervalIntegral.integral_congr
    intro s hs
    simp only [Set.uIcc_of_le (by norm_num : (0:ℝ) ≤ 1/2), Set.mem_Icc] at hs
    dsimp only
    rw [if_pos hs.2]
  rw [h1]
  -- Pull out constant 2 (as ℂ-scalar); provide f explicitly for unification
  have h2 : ∫ s in (0:ℝ)..(1/2), 2 * derivWithin α' (Set.Icc 0 1) (2 * s) =
      2 * ∫ s in (0:ℝ)..(1/2), derivWithin α' (Set.Icc 0 1) (2 * s) :=
    intervalIntegral.integral_const_mul 2 (fun s => derivWithin α' (Set.Icc 0 1) (2 * s))
  rw [h2]
  -- Change of variables u = 2s: ∫ 0..1/2, f(2s) = 2⁻¹ • ∫ 0..1, f(s)
  have h3 : ∫ s in (0:ℝ)..(1/2), derivWithin α' (Set.Icc 0 1) (2 * s) =
      (2:ℝ)⁻¹ • ∫ s in (0:ℝ)..(1:ℝ), derivWithin α' (Set.Icc 0 1) s := by
    have key : ∫ s in (0:ℝ)..(1/2), derivWithin α' (Set.Icc 0 1) (2 * s) =
        (2:ℝ)⁻¹ • ∫ s in (2:ℝ)*0..(2:ℝ)*(1/2), derivWithin α' (Set.Icc 0 1) s :=
      intervalIntegral.integral_comp_mul_left
        (derivWithin α' (Set.Icc 0 1)) (two_ne_zero' ℝ)
    simp only [mul_zero, show (2:ℝ) * (1/2) = 1 from by norm_num] at key
    exact key
  rw [h3, intervalIntegral.integral_derivWithin_Icc_of_contDiffOn_Icc hα' zero_le_one]
  -- Simplify 2 * (2⁻¹ • v) = v in ℂ
  rw [Complex.real_smul]
  push_cast
  field_simp

/-- The integrand `Q(h t) * deriv h t` equals `2 * (Q(α'(2t)) * deriv α'(2t))` on `[0, 1/2]`,
using `h t = α'(2t)` and the chain rule `deriv h t = 2 * deriv α'(2t)`. -/
theorem subst_alpha_chain_rule_left
    {Q : ℂ → ℂ} {α' h : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1 / 2), h t = α' (2 * t)) :
    (∫ t in (0 : ℝ)..(1 / 2 : ℝ), Q (h t) * deriv h t) =
      (∫ t in (0 : ℝ)..(1 / 2 : ℝ), 2 * (Q (α' (2 * t)) * deriv α' (2 * t))) := by
  apply intervalIntegral.integral_congr_ae
  have hne : ∀ᵐ t ∂MeasureTheory.volume, t ≠ (1 / 2 : ℝ) := by
    rw [MeasureTheory.ae_iff]
    simp [MeasureTheory.measure_singleton]
  filter_upwards [hne] with t hne_t ht_uIoc
  rw [Set.uIoc_of_le (by norm_num : (0 : ℝ) ≤ 1 / 2)] at ht_uIoc
  have htIoo : t ∈ Set.Ioo (0 : ℝ) (1 / 2) :=
    ⟨ht_uIoc.1, lt_of_le_of_ne ht_uIoc.2 hne_t⟩
  have hht : h t = α' (2 * t) := hh_left t (Set.Ioo_subset_Icc_self htIoo)
  have hderiv_h_eq : deriv h t = deriv (fun s => α' (2 * s)) t := by
    apply Filter.EventuallyEq.deriv_eq
    apply Filter.eventually_of_mem (Ioo_mem_nhds htIoo.1 htIoo.2)
    intro s hs
    exact hh_left s ⟨le_of_lt hs.1, le_of_lt hs.2⟩
  have h2t_mem : 2 * t ∈ Set.Ioo (0 : ℝ) 1 :=
    ⟨by linarith [htIoo.1], by linarith [htIoo.2]⟩
  have hIcc_nhds : Set.Icc (0 : ℝ) 1 ∈ nhds (2 * t) :=
    Filter.mem_of_superset (Ioo_mem_nhds h2t_mem.1 h2t_mem.2) Set.Ioo_subset_Icc_self
  have hdα_at : DifferentiableAt ℝ α' (2 * t) :=
    (hα'.differentiableOn (by norm_num)).differentiableAt hIcc_nhds
  have hd2 : HasDerivAt (fun s : ℝ => 2 * s) (2 : ℝ) t := by
    have := (hasDerivAt_id t).const_mul (2 : ℝ); simpa using this
  have hchain : deriv (fun s => α' (2 * s)) t = (2 : ℝ) • deriv α' (2 * t) :=
    (hdα_at.hasDerivAt.scomp t hd2).deriv
  rw [hht, hderiv_h_eq, hchain,
      show (2 : ℝ) • deriv α' (2 * t) = (2 : ℂ) * deriv α' (2 * t) from by
        rw [Algebra.smul_def]; norm_cast]
  ring

/-- Change of variables `u = 2t`: the integral `∫₀^{1/2} 2*(Q(α'(2t))*α''(2t)) dt`
equals `∫₀¹ Q(α'(t))*α''(t) dt`. -/
theorem int_two_alpha_eq_alpha
    {Q : ℂ → ℂ} {α' h : ℝ → ℂ}
    (_hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (_hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1 / 2), h t = α' (2 * t)) :
    (∫ t in (0:ℝ)..(1/2:ℝ), 2 * (Q (α' (2*t)) * deriv α' (2*t))) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) := by
  calc ∫ t in (0:ℝ)..(1/2:ℝ), 2 * (Q (α' (2*t)) * deriv α' (2*t))
      = 2 * ∫ t in (0:ℝ)..(1/2:ℝ), Q (α' (2*t)) * deriv α' (2*t) :=
        intervalIntegral.integral_const_mul 2 _
    _ = ∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t := by
        rw [show (2:ℂ) = ((2:ℝ):ℂ) from by norm_cast, ← Complex.real_smul]
        have hkey := intervalIntegral.smul_integral_comp_mul_left
          (fun t => Q (α' t) * deriv α' t) (2:ℝ) (a := 0) (b := 1/2)
        simp only [mul_zero, show (2:ℝ) * (1/2:ℝ) = 1 from by norm_num] at hkey
        exact hkey

/-- The contour integral `∫₀^{1/2} Q(h t) * h'(t) dt` equals `∫₀¹ Q(α'(t)) * α''(t) dt`
when `h t = α'(2t)` on `[0, 1/2]`, via the chain rule and change of variables. -/
theorem integral_subst_alpha_left_half
    {Q : ℂ → ℂ} {α' h : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1 / 2), h t = α' (2 * t)) :
    (∫ t in (0:ℝ)..(1/2:ℝ), Q (h t) * deriv h t) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) := by
  have h1 := subst_alpha_chain_rule_left (Q := Q) hα' hh hh_left
  have h2 := int_two_alpha_eq_alpha (Q := Q) (h := h) hα' hh hh_left
  exact h1.trans h2

/-- Variant of `integral_subst_alpha_left_half` carrying the full analytic data of the
concatenation; `∫₀^{1/2} Q(h t) * h'(t) dt = ∫₀¹ Q(α'(t)) * α''(t) dt`. -/
theorem flat_left_int_subst_alpha
    {Q : ℂ → ℂ} {a : ℂ}
    (_hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (_hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (_hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (_hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (_h_match : α' 1 = β' 0)
    (_hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (_hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0)
    {h : ℝ → ℂ}
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1 / 2), h t = α' (2 * t)) :
    (∫ t in (0:ℝ)..(1/2:ℝ), Q (h t) * deriv h t) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) :=
    integral_subst_alpha_left_half hα' hh hh_left

/-- The integrand `Q(γ t) * derivWithin γ (Icc 0 1) t` is continuous on `[0, 1/2]`,
where `γ` is the piecewise-integral primitive of the concatenated velocity. -/
theorem integrand_dw_cont_on_left_half
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContinuousOn
      (fun t : ℝ =>
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          derivWithin (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) (Set.Icc 0 1) t)
      (Set.Icc 0 (1/2)) := by
  set γ := fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
      (if s ≤ (1:ℝ)/2
        then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
        else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) with hγ_def
  have hγ_c1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1) :=
    contDiffOn_piecewiseConcat_integral hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have hγ_avoid : ∀ t ∈ Set.Icc (0:ℝ) (1/2), γ t ≠ a := by
    intro t ht
    have hγt := flat_left_h_eq_alpha hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match
        hα'_deriv hβ'_deriv t ht
    rw [show γ t = α' 0 + ∫ s in (0:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) from rfl, hγt]
    exact hα'_avoid (2*t) ⟨by linarith [ht.1], by linarith [ht.2]⟩
  have hγ_cont : ContinuousOn γ (Set.Icc 0 (1/2)) :=
    hγ_c1.continuousOn.mono (Set.Icc_subset_Icc_right (by norm_num))
  have hQγ_cont : ContinuousOn (fun t => Q (γ t)) (Set.Icc 0 (1/2)) :=
    hQ_an.continuousOn.comp hγ_cont (fun t ht => by
      simp only [Set.mem_diff, Set.mem_univ, Set.mem_singleton_iff, true_and]
      exact hγ_avoid t ht)
  have hγ_dw_cont : ContinuousOn (derivWithin γ (Set.Icc 0 1)) (Set.Icc 0 (1/2)) :=
    (hγ_c1.continuousOn_derivWithin uniqueDiffOn_Icc_zero_one le_rfl).mono
      (Set.Icc_subset_Icc_right (by norm_num))
  exact hQγ_cont.mul hγ_dw_cont

/-- The integrand `Q(γ t) * deriv γ t` is interval-integrable on `[0, 1/2]`, following
from continuity of the `derivWithin` version and the fact that `deriv = derivWithin` in
the interior of `[0, 1]`. -/
theorem flat_ftc_intintegrable_left_half
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    IntervalIntegrable
      (fun t : ℝ =>
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t)
      MeasureTheory.volume 0 (1/2) := by
  have h_cont :=
    integrand_dw_cont_on_left_half hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_int_dw :
      IntervalIntegrable
        (fun t : ℝ =>
          Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
                (if s ≤ (1:ℝ)/2
                  then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                  else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
            derivWithin (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
                (if s ≤ (1:ℝ)/2
                  then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                  else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) (Set.Icc 0 1) t)
        MeasureTheory.volume 0 (1/2) :=
    h_cont.intervalIntegrable_of_Icc (by norm_num)
  apply h_int_dw.congr_ae
  rw [Set.uIoc_of_le (by norm_num : (0:ℝ) ≤ 1/2)]
  refine MeasureTheory.ae_restrict_of_ae_eq_of_ae_restrict MeasureTheory.Ioo_ae_eq_Ioc ?_
  filter_upwards [MeasureTheory.ae_restrict_mem measurableSet_Ioo] with t ht
  have hmem : Set.Icc (0:ℝ) 1 ∈ nhds t :=
    Icc_mem_nhds (by linarith [ht.1]) (by linarith [ht.2])
  simp [derivWithin_of_mem_nhds hmem]

/-- The contour integral `∫₀^{1/2} Q(γ t) * γ'(t) dt` along the piecewise-integral primitive `γ`
equals `∫₀¹ Q(α'(t)) * α''(t) dt`: on the left half `γ t = α'(2t)`, and a change of variables
`u = 2t` transforms the integral back to the `α'`-parametrisation on `[0, 1]`. -/
theorem flat_ftc_left_half_int_eq
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    (∫ t in (0:ℝ)..(1/2:ℝ),
        Q ((fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) *
          deriv (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
              (if s ≤ (1:ℝ)/2
                then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
                else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1))) t) =
      (∫ t in (0:ℝ)..1, Q (α' t) * deriv α' t) := by
  set h : ℝ → ℂ := fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
            (if s ≤ (1:ℝ)/2
              then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
              else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)) with hh_def
  have h_smooth : ContDiffOn ℝ 1 h (Set.Icc 0 1) :=
    contDiffOn_piecewiseConcat_integral hQ_an hα' hα'_avoid hβ' hβ'_avoid
      h_match hα'_deriv hβ'_deriv
  have h_eq : ∀ t ∈ Set.Icc (0:ℝ) (1/2), h t = α' (2*t) :=
    flat_left_h_eq_alpha hQ_an hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  exact flat_left_int_subst_alpha (Q := Q) hQ_an hα' hα'_avoid hβ' hβ'_avoid
    h_match hα'_deriv hβ'_deriv h_smooth h_eq

end Library.Analysis.ResidueTheorem.PathConcatLeftHalf
