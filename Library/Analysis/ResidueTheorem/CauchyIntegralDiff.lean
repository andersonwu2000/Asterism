import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Calculus.ParametricIntervalIntegral
import Mathlib.MeasureTheory.Integral.CircleIntegral

/-!
# Differentiability of the Cauchy kernel circle integral outside the circle

This file establishes that the circle integral `∮ w in C(c, r), g w / (w - ζ)` is differentiable
in `ζ` at points strictly outside the circle of radius `r` centred at `c`. The key ingredient is
the parametric Leibniz rule
(`intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le`), applied after obtaining
uniform bounds on the integrand's $\zeta$-derivative.

## Main statements

- `circle_int_param_diff_outside_at`: the circle integral of `g w / (w - ζ)` is
  `DifferentiableAt` in `ζ` at every exterior point.
- `cauchy_kernel_diff_at_outside`: the Cauchy kernel integral
  `-(2πi)⁻¹ * ∮ f w / (w - ζ)` is differentiable at exterior points.

## Implementation notes

The argument proceeds through several auxiliary lemmas:
- `circle_integrand_intvlint_outside` establishes `IntervalIntegrable` for the integrand.
- `circle_zeta_partial_aemeas_at_z` gives `AEStronglyMeasurable` for the $\zeta$-partial
  integrand.
- `circle_zeta_partial_hasderiv` computes the pointwise `HasDerivAt` in `ζ`.
- `g_bounded_on_sphere` extracts a uniform bound on `‖g‖` from compactness.
- `circle_dist_lower_bound_near_outside` gives a positive lower bound on `‖w - ζ‖` near an
  exterior point via the reverse triangle inequality.
- `circle_zeta_partial_unif_bound_near` combines the above into the domination bound.
-/

open Filter Topology

namespace Library.Analysis.ResidueTheorem.CauchyIntegralDiff

/-- The Cauchy circle integrand
`θ ↦ deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ))`
is `IntervalIntegrable` on `[0, 2π]` for every `g` continuous on the sphere and every
exterior point `ζ` with `r < dist ζ c`. -/
theorem circle_integrand_intvlint_outside
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r)) :
    ∀ ζ : ℂ, r < dist ζ c →
      IntervalIntegrable
        (fun θ => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ)))
        MeasureTheory.volume 0 (2 * Real.pi) := by
  intro ζ hζ
  apply ContinuousOn.intervalIntegrable
  have hderiv : ∀ θ : ℝ, deriv (circleMap c r) θ = circleMap 0 r θ * Complex.I :=
    fun θ => (hasDerivAt_circleMap c r θ).deriv
  simp_rw [hderiv]
  apply ContinuousOn.smul
  · exact ((continuous_circleMap 0 r).mul continuous_const).continuousOn
  · apply ContinuousOn.div
    · exact hg.comp (continuous_circleMap c r).continuousOn
        (fun θ _ => circleMap_mem_sphere c hr.le θ)
    · exact ((continuous_circleMap c r).sub continuous_const).continuousOn
    · intro θ _ heq
      have hmem := circleMap_mem_sphere c hr.le θ
      rw [Metric.mem_sphere] at hmem
      have hze : circleMap c r θ = ζ := sub_eq_zero.mp heq
      have hd : dist ζ c = r := hze ▸ hmem
      linarith


/-- The `ζ`-partial circle integrand
`θ ↦ deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - z) ^ 2)`
is `AEStronglyMeasurable` on `[0, 2π]` for each exterior point `z` with `r < dist z c`. -/
theorem circle_zeta_partial_aemeas_at_z
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r))
    (z : ℂ) (hz : r < dist z c) :
    MeasureTheory.AEStronglyMeasurable
      (fun θ => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - z) ^ 2))
      (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) (2 * Real.pi))) := by
  apply Continuous.aestronglyMeasurable
  simp_rw [deriv_circleMap]
  apply Continuous.smul
  · exact (continuous_circleMap 0 r).mul continuous_const
  · apply Continuous.div
    · exact hg.comp_continuous (continuous_circleMap c r)
          (fun θ => circleMap_mem_sphere c hr.le θ)
    · exact ((continuous_circleMap c r).sub continuous_const).pow 2
    · intro θ
      apply pow_ne_zero
      intro heq
      have hmem := circleMap_mem_sphere c hr.le θ
      rw [Metric.mem_sphere] at hmem
      have hdc : dist z c = r := by
        have hq := sub_eq_zero.mp heq; rw [← hq]; exact hmem
      linarith


/-- Pointwise derivative in `ζ` for the Cauchy circle integrand: for each `θ : ℝ` and each
exterior point `ζ` with `r < dist ζ c`, the map
`ζ' ↦ deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ'))`
has derivative
`deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2)` at `ζ`. -/
theorem circle_zeta_partial_hasderiv
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r) :
    ∀ θ : ℝ, ∀ ζ : ℂ, r < dist ζ c →
      HasDerivAt
        (fun ζ' => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ')))
        (deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2))
        ζ := by
  intro θ ζ hζ
  have hne : circleMap c r θ - ζ ≠ 0 := sub_ne_zero.mpr (by
    intro heq
    rw [← heq, dist_comm] at hζ
    simp [circleMap, abs_of_pos hr] at hζ)
  have h2 : HasDerivAt (fun ζ' => circleMap c r θ - ζ') (-1) ζ :=
    by simpa using (hasDerivAt_id ζ).const_sub (circleMap c r θ)
  simpa [zero_mul, zero_sub, neg_mul, neg_neg] using
    ((hasDerivAt_const ζ _).div h2 hne).const_smul (deriv (circleMap c r) θ)


/-- A continuous function `g` on a compact sphere is bounded: there exists `Mg ≥ 0` with
`‖g w‖ ≤ Mg` for all `w` on the sphere. -/
theorem g_bounded_on_sphere
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r)) :
    ∃ Mg : ℝ, 0 ≤ Mg ∧ ∀ w ∈ Metric.sphere c r, ‖g w‖ ≤ Mg := by
  have hcomp : IsCompact (Metric.sphere c r) := isCompact_sphere c r
  have hne : (Metric.sphere c r).Nonempty := NormedSpace.sphere_nonempty.mpr hr.le
  obtain ⟨x, hx, hxmax⟩ := hcomp.exists_isMaxOn hne hg.norm
  exact ⟨‖g x‖, norm_nonneg _, fun w hw => hxmax hw⟩


/-- For `z` exterior to the circle of radius `r` centred at `c`, every `ζ` in the half-gap
ball `Metric.ball z ((dist z c - r) / 2)` satisfies
`(dist z c - r) / 2 ≤ ‖circleMap c r θ - ζ‖` for all `θ : ℝ`,
by the reverse triangle inequality. -/
theorem circle_dist_lower_bound_near_outside
    {c : ℂ} {r : ℝ} (hr : 0 < r) (z : ℂ) (_hz : r < dist z c) :
    ∀ ζ ∈ Metric.ball z ((dist z c - r) / 2), ∀ θ : ℝ,
      (dist z c - r) / 2 ≤ ‖circleMap c r θ - ζ‖ := by
  intro ζ hζ θ
  have hζ_lt : dist ζ z < (dist z c - r) / 2 := by rwa [Metric.mem_ball] at hζ
  have hw_dist : dist z c - r ≤ ‖circleMap c r θ - z‖ := by
    have hcirc : ‖circleMap c r θ - c‖ = r := by
      simp [circleMap, hr.le]
    have tri := dist_triangle z (circleMap c r θ) c
    rw [dist_eq_norm, dist_eq_norm (circleMap c r θ) c] at tri
    linarith [norm_sub_rev z (circleMap c r θ), dist_eq_norm z (circleMap c r θ),
              norm_sub_rev z c, dist_eq_norm z c]
  have tri2 : ‖circleMap c r θ - z‖ - ‖ζ - z‖ ≤ ‖circleMap c r θ - ζ‖ := by
    have h := norm_sub_norm_le (circleMap c r θ - z) (ζ - z)
    simp only [sub_sub_sub_cancel_right] at h
    linarith
  linarith [dist_eq_norm ζ z]


/-- Uniform domination bound for the `ζ`-partial integrand: given `g` continuous on the sphere
and `z` exterior to the circle, there exists `M : ℝ` bounding
`‖deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2)‖`
uniformly over all `ζ` in `Metric.ball z ((dist z c - r) / 2)` and all `θ : ℝ`.
The bound `M = r * Mg / δ²` combines `‖deriv (circleMap c r) θ‖ = r`,
a sup-norm bound from `g_bounded_on_sphere`, and `circle_dist_lower_bound_near_outside`. -/
theorem circle_zeta_partial_unif_bound_near
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r))
    (z : ℂ) (hz : r < dist z c) :
    ∃ M : ℝ, ∀ ζ ∈ Metric.ball z ((dist z c - r) / 2), ∀ θ : ℝ,
      ‖deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2)‖ ≤ M := by
  set δ : ℝ := (dist z c - r) / 2 with hδ_def
  have hδ_pos : 0 < δ := by rw [hδ_def]; linarith
  have h_g_bdd := g_bounded_on_sphere hr hg
  have h_dist_lb := circle_dist_lower_bound_near_outside hr z hz
  obtain ⟨Mg, hMg0, hMg⟩ := h_g_bdd
  refine ⟨r * Mg / δ ^ 2, fun ζ hζ θ => ?_⟩
  have hθ_sphere : circleMap c r θ ∈ Metric.sphere c r := circleMap_mem_sphere c hr.le θ
  have hg_bound : ‖g (circleMap c r θ)‖ ≤ Mg := hMg _ hθ_sphere
  have hd : δ ≤ ‖circleMap c r θ - ζ‖ := h_dist_lb ζ hζ θ
  have hd_pos : 0 < ‖circleMap c r θ - ζ‖ := lt_of_lt_of_le hδ_pos hd
  have h_dn : ‖deriv (circleMap c r) θ‖ = r := by
    rw [deriv_circleMap, norm_mul, norm_circleMap_zero, Complex.norm_I, mul_one, abs_of_pos hr]
  calc ‖deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ) ^ 2)‖
      = r * (‖g (circleMap c r θ)‖ / ‖circleMap c r θ - ζ‖ ^ 2) := by
        rw [norm_smul, h_dn, norm_div, norm_pow]
    _ ≤ r * (Mg / δ ^ 2) := by
        gcongr
    _ = r * Mg / δ ^ 2 := by ring


/-- The circle integral `∮ w in C(c, r), g w / (w - ζ)` is `DifferentiableAt ℂ` in `ζ` at
every exterior point `z` with `r < dist z c`. The proof applies the parametric Leibniz rule
(`intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le`) with the neighbourhood
`Metric.ball z ((dist z c - r) / 2)`, which stays in the exterior region. -/
theorem circle_int_param_diff_outside_at
    {g : ℂ → ℂ} {c : ℂ} {r : ℝ} (hr : 0 < r)
    (hg : ContinuousOn g (Metric.sphere c r))
    (z : ℂ) (hz : r < dist z c) :
    DifferentiableAt ℂ (fun ζ => ∮ w in C(c, r), g w / (w - ζ)) z := by
  set δ : ℝ := (dist z c - r) / 2 with hδ_def
  have hδ_pos : 0 < δ := by rw [hδ_def]; linarith
  have hball_out : ∀ ζ ∈ Metric.ball z δ, r < dist ζ c := by
    intro ζ hζ
    have hdz : dist ζ z < δ := Metric.mem_ball.mp hζ
    have htri : dist z c ≤ dist z ζ + dist ζ c := dist_triangle z ζ c
    have hcomm : dist z ζ = dist ζ z := dist_comm _ _
    rw [hcomm] at htri
    linarith
  have hs_mem : Metric.ball z δ ∈ 𝓝 z := Metric.ball_mem_nhds z hδ_pos
  have h_integrable := circle_integrand_intvlint_outside hr hg
  have h_partial_meas := circle_zeta_partial_aemeas_at_z hr hg z hz
  have h_pointwise := @circle_zeta_partial_hasderiv g c r hr
  obtain ⟨M, h_bound⟩ := circle_zeta_partial_unif_bound_near hr hg z hz
  have h_meas_near : ∀ᶠ ζ in 𝓝 z, MeasureTheory.AEStronglyMeasurable
      (fun θ => deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ)))
      (MeasureTheory.volume.restrict (Set.uIoc (0:ℝ) (2 * Real.pi))) := by
    filter_upwards [hs_mem] with ζ hζ
    have h := (h_integrable ζ (hball_out ζ hζ)).aestronglyMeasurable
    rwa [Set.uIoc_of_le Real.two_pi_pos.le]
  have h_leibniz := intervalIntegral.hasDerivAt_integral_of_dominated_loc_of_deriv_le
    (𝕜 := ℂ) (a := (0:ℝ)) (b := 2 * Real.pi) (μ := MeasureTheory.volume)
    (s := Metric.ball z δ) (bound := fun _ => M)
    hs_mem h_meas_near (h_integrable z hz)
    h_partial_meas
    (by
      apply MeasureTheory.ae_of_all
      intro θ _hθ ζ hζ
      exact h_bound ζ hζ θ)
    intervalIntegrable_const
    (by
      apply MeasureTheory.ae_of_all
      intro θ _hθ ζ hζ
      exact h_pointwise θ ζ (hball_out ζ hζ))
  have hcast : (fun ζ => ∮ w in C(c, r), g w / (w - ζ)) =
      (fun ζ => ∫ θ in (0 : ℝ)..(2 * Real.pi),
        deriv (circleMap c r) θ • (g (circleMap c r θ) / (circleMap c r θ - ζ))) := by
    funext ζ; rfl
  rw [hcast]
  exact h_leibniz.2.differentiableAt


/-- The Cauchy kernel circle integral
`ζ ↦ -((2 * π * I)⁻¹ * ∮ w in C(z₀, ε), f w / (w - ζ))`
is `DifferentiableAt ℂ` at every `z` strictly outside the circle of radius `ε`,
assuming `f` is analytic on the punctured ball `Metric.ball z₀ R \ {z₀}`
and `ε < dist z z₀`. -/
theorem cauchy_kernel_diff_at_outside
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (ε : ℝ) (hε0 : 0 < ε) (hεR : ε < R)
    (z : ℂ) (hzne : z ≠ z₀) (hεd : ε < dist z z₀) :
    DifferentiableAt ℂ
      (fun ζ => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, ε), f w / (w - ζ))) z := by
  have hsph : Metric.sphere z₀ ε ⊆ Metric.ball z₀ R \ ({z₀} : Set ℂ) := by
    intro w hw
    have hwdist : dist w z₀ = ε := Metric.mem_sphere.mp hw
    refine ⟨Metric.mem_ball.mpr ?_, ?_⟩
    · rw [hwdist]; exact hεR
    · intro hwz; subst hwz
      have : (0 : ℝ) = ε := by simpa [dist_self] using hwdist
      linarith
  have hgcont : ContinuousOn f (Metric.sphere z₀ ε) :=
    hf.continuousOn.mono hsph
  have h_circle_diff :
      DifferentiableAt ℂ (fun ζ => ∮ w in C(z₀, ε), f w / (w - ζ)) z :=
    circle_int_param_diff_outside_at hε0 hgcont z hεd
  exact (h_circle_diff.const_mul ((2 * (Real.pi : ℂ) * Complex.I)⁻¹)).neg

end Library.Analysis.ResidueTheorem.CauchyIntegralDiff
