import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.MeasureTheory.Integral.CircleIntegral

/-!
# Cauchy kernel decay at infinity

This file establishes that Cauchy kernel circle integrals
`∮ f w / (w - z)` over `C(z₀, R/2)` tend to zero along the cocompact filter on `ℂ`,
given that `f` is analytic on the punctured ball `Metric.ball z₀ R \ {z₀}`.

## Main statements

- `uniform_bound_f_on_sphere`: analyticity on the punctured ball implies a uniform bound for
  `‖f‖` on the sphere `Metric.sphere z₀ (R/2)`.
- `circle_integral_norm_le_decay_eventually`: the circle integral norm is eventually bounded
  by `M / (‖z - z₀‖ - R/2)` along the cocompact filter.
- `circle_integral_tendsto_zero_at_cocompact`: the circle integral tends to `0` along the
  cocompact filter.
- `inner_integral_tendsto_zero`: the full scaled Cauchy kernel expression tends to `0`
  at cocompact.

## Implementation notes

Several lemmas carry a hypothesis `P` encoding the Cauchy kernel representation formula.
It is unused in those proofs and serves only to give all lemmas a uniform signature
matching the parent goal.
-/

namespace Library.Analysis.ResidueTheorem.CauchyKernelDecay

/-- If `f` is analytic on the punctured ball `Metric.ball z₀ R \ {z₀}`, then `‖f‖` is
uniformly bounded on the sphere `Metric.sphere z₀ (R/2)`. The bound is obtained via
compactness of the sphere and continuity of `f`. -/
theorem uniform_bound_f_on_sphere
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (_hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    ∃ C : ℝ, 0 ≤ C ∧ ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C := by
  have hR2 : (0 : ℝ) < R / 2 := by linarith
  have hcomp : IsCompact (Metric.sphere z₀ (R/2)) := isCompact_sphere z₀ (R/2)
  have hnon : (Metric.sphere z₀ (R/2)).Nonempty := by
    refine ⟨z₀ + (R/2 : ℝ), ?_⟩
    simp; linarith
  have hsub : Metric.sphere z₀ (R/2) ⊆ Metric.ball z₀ R \ {z₀} := by
    intro w hw
    rw [Metric.mem_sphere] at hw
    constructor
    · rw [Metric.mem_ball]; linarith [hw.symm ▸ le_refl (R/2)]
    · simp only [Set.mem_singleton_iff]
      intro heq; simp [heq] at hw; linarith
  have hcont : ContinuousOn (fun w => ‖f w‖) (Metric.sphere z₀ (R/2)) :=
    (hf.continuousOn.mono hsub).norm
  obtain ⟨x, hx, hmax⟩ := hcomp.exists_isMaxOn hnon hcont
  exact ⟨‖f x‖, norm_nonneg _, fun w hw => hmax hw⟩

/-- For any uniform bound `C` on `‖f‖` over `Metric.sphere z₀ (R/2)`, the condition
`R/2 < ‖z - z₀‖` holds eventually along the cocompact filter on `ℂ`. -/
theorem cocompact_eventually_far_from_z0
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (_hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (_hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (_hC0 : 0 ≤ C)
    (_hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∀ᶠ z in Filter.cocompact ℂ, R/2 < ‖z - z₀‖ := by
  apply Filter.mem_of_superset (isCompact_closedBall z₀ (R/2)).compl_mem_cocompact
  intro z hz
  simp only [Set.mem_compl_iff, Metric.mem_closedBall, not_le] at hz
  simp only [Set.mem_setOf_eq]
  rwa [← Complex.dist_eq]

/-- For every `M : ℝ`, the function `z ↦ M / (‖z - z₀‖ - R/2)` tends to `0` along the
cocompact filter on `ℂ`. -/
theorem tendsto_const_div_dist_zero
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (_hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (_hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    ∀ M : ℝ, Filter.Tendsto
      (fun z : ℂ => M / (‖z - z₀‖ - R/2))
      (Filter.cocompact ℂ) (nhds 0) := by
  intro M
  have h_norm : Filter.Tendsto (fun z : ℂ => ‖z - z₀‖) (Filter.cocompact ℂ) Filter.atTop :=
    tendsto_norm_cocompact_atTop.comp
      (Homeomorph.addRight (-z₀)).toCocompactMap.cocompact_tendsto'
  have h_sub : Filter.Tendsto (fun z : ℂ => ‖z - z₀‖ - R / 2)
      (Filter.cocompact ℂ) Filter.atTop := by
    simpa [sub_eq_add_neg, neg_div] using
      Filter.tendsto_atTop_add_const_right (Filter.cocompact ℂ) (-R / 2) h_norm
  have h_inv : Filter.Tendsto (fun x : ℝ => M / x) Filter.atTop (nhds 0) := by
    simpa [div_eq_mul_inv] using (tendsto_const_nhds (x := M)).mul tendsto_inv_atTop_zero
  exact h_inv.comp h_sub

/-- Pointwise norm bound for the Cauchy kernel integrand: if `w ∈ Metric.sphere z₀ (R/2)`
and `R/2 < ‖z - z₀‖`, then `‖f w / (w - z)‖ ≤ C / (‖z - z₀‖ - R/2)`. The denominator
lower bound follows from the reverse triangle inequality. -/
theorem pointwise_kernel_norm_bound
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (_hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (_hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (hC0 : 0 ≤ C)
    (hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∀ z : ℂ, R/2 < ‖z - z₀‖ →
      ∀ w ∈ Metric.sphere z₀ (R/2),
    ‖f w / (w - z)‖ ≤ C / (‖z - z₀‖ - R/2) := by
  intro z hz w hw
  have hw_norm : ‖w - z₀‖ = R / 2 := by
    rw [← dist_eq_norm]; exact Metric.mem_sphere.mp hw
  have hwz_pos : 0 < ‖z - z₀‖ - R / 2 := by linarith
  have hwz_lb : ‖z - z₀‖ - R / 2 ≤ ‖w - z‖ := by
    have h1 := norm_add_le (z - w) (w - z₀)
    simp only [sub_add_sub_cancel] at h1
    rw [norm_sub_rev z w, hw_norm] at h1
    linarith
  have hwz_lt : 0 < ‖w - z‖ := lt_of_lt_of_le hwz_pos hwz_lb
  rw [norm_div]
  gcongr
  · exact hC w hw

/-- Circle integral norm bound via the length-times-sup estimate: when `R/2 < ‖z - z₀‖`,
the norm `‖∮ w in C(z₀, R/2), f w / (w - z)‖` is at most
`2 * Real.pi * (R/2) * C / (‖z - z₀‖ - R/2)`. -/
theorem pointwise_circle_int_div_bound
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (hC0 : 0 ≤ C)
    (hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∀ z : ℂ, R/2 < ‖z - z₀‖ →
      ‖∮ w in C(z₀, R/2), f w / (w - z)‖
        ≤ 2 * Real.pi * (R/2) * C / (‖z - z₀‖ - R/2) := by
  intro z hz
  have hr : (0:ℝ) ≤ R/2 := by linarith
  have h_pointwise_kernel_norm_bound :=
    pointwise_kernel_norm_bound hR hf P hP C hC0 hC z hz
  have h_int :=
    circleIntegral.norm_integral_le_of_norm_le_const hr h_pointwise_kernel_norm_bound
  calc ‖∮ w in C(z₀, R/2), f w / (w - z)‖
      ≤ 2 * Real.pi * (R/2) * (C / (‖z - z₀‖ - R/2)) := h_int
    _ = 2 * Real.pi * (R/2) * C / (‖z - z₀‖ - R/2) := by ring

/-- Given a uniform bound `C` on `‖f‖` over `Metric.sphere z₀ (R/2)`, there exists `M ≥ 0`
such that `‖∮ w in C(z₀, R/2), f w / (w - z)‖ ≤ M / (‖z - z₀‖ - R/2)` holds eventually
along the cocompact filter. The constant is `M = 2 * Real.pi * (R/2) * C`. -/
theorem cocompact_decay_from_uniform
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (hC0 : 0 ≤ C)
    (hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∃ M : ℝ, 0 ≤ M ∧ ∀ᶠ z in Filter.cocompact ℂ,
      ‖∮ w in C(z₀, R/2), f w / (w - z)‖ ≤ M / (‖z - z₀‖ - R/2) := by
  refine ⟨2 * Real.pi * (R/2) * C, by positivity, ?_⟩
  filter_upwards [cocompact_eventually_far_from_z0 hR hf P hP C hC0 hC] with z hz
  exact pointwise_circle_int_div_bound hR hf P hP C hC0 hC z hz

/-- There exists `M ≥ 0` such that `‖∮ w in C(z₀, R/2), f w / (w - z)‖ ≤ M / (‖z - z₀‖ - R/2)`
holds eventually along the cocompact filter. Combines the uniform bound from
`uniform_bound_f_on_sphere` with the estimate from `cocompact_decay_from_uniform`. -/
theorem circle_integral_norm_le_decay_eventually
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    ∃ M : ℝ, 0 ≤ M ∧ ∀ᶠ z in Filter.cocompact ℂ,
      ‖∮ w in C(z₀, R/2), f w / (w - z)‖ ≤ M / (‖z - z₀‖ - R/2) := by
  have h_bound := uniform_bound_f_on_sphere hR hf P hP
  obtain ⟨C, hC0, hC⟩ := h_bound
  exact cocompact_decay_from_uniform hR hf P hP C hC0 hC

/-- The circle integral `∮ w in C(z₀, R/2), f w / (w - z)` tends to `0` along the cocompact
filter on `ℂ`. This follows by squeezing between `0` and the decay bound
`M / (‖z - z₀‖ - R/2) → 0`. -/
theorem circle_integral_tendsto_zero_at_cocompact
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    Filter.Tendsto
      (fun z => ∮ w in C(z₀, R/2), f w / (w - z))
      (Filter.cocompact ℂ) (nhds 0) := by
  have h1 := circle_integral_norm_le_decay_eventually hR hf P hP
  have h2 := tendsto_const_div_dist_zero hR hf P hP
  obtain ⟨M, _hM0, hMevent⟩ := h1
  refine (tendsto_zero_iff_norm_tendsto_zero).mpr ?_
  refine squeeze_zero' (Filter.Eventually.of_forall (fun z => norm_nonneg _)) hMevent (h2 M)

/-- The scaled Cauchy kernel `-(2 * π * I)⁻¹ * ∮ f w / (w - z)` tends to `0` along the
cocompact filter on `ℂ`. Follows from `circle_integral_tendsto_zero_at_cocompact` via
`Filter.Tendsto.const_mul` and `Filter.Tendsto.neg`. -/
theorem inner_integral_tendsto_zero
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    Filter.Tendsto
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z)))
      (Filter.cocompact ℂ) (nhds 0) := by
  have h_int := circle_integral_tendsto_zero_at_cocompact hR hf P hP
  have h_scaled := (h_int.const_mul ((2 * (Real.pi : ℂ) * Complex.I)⁻¹)).neg
  simpa using h_scaled

end Library.Analysis.ResidueTheorem.CauchyKernelDecay
