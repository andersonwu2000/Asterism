import Library.Analysis.ResidueTheorem.CauchyKernelSplit

/-!
# Holomorphic part of the Cauchy kernel

This file establishes analyticity of the Cauchy integral kernel as a function of its
evaluation point. The key insight is a local fixed-radius substitution: for each base point
$z_1$ in the punctured-ball domain, the variable-radius integral
$(2\pi i)^{-1}\oint_{C(z_0,(d(z,z_0)+R)/2)} f(w)/(w-z)\,dw$
agrees with a fixed-radius integral near $z_1$, and Mathlib's
`hasFPowerSeriesOn_cauchy_integral` then yields analyticity.

## Main statements

- `analyticOn_cauchy_kernel`: the variable-radius Cauchy kernel is analytic on
  `Metric.ball z₀ R` whenever `f` is analytic on the punctured ball `Metric.ball z₀ R \ {z₀}`.
- `exists_analyticOn_cauchy_kernel`: an analytic witness $g$ on `Metric.ball z₀ R` exists
  that agrees with every valid fixed-radius Cauchy integral for $z$ in the ball.
-/

open Library.Analysis.ResidueTheorem.CauchyKernelSplit

namespace Library.Analysis.ResidueTheorem.HolomorphicPart

/-- The Cauchy integral $(2\pi i)^{-1}\oint_{C(z_0,r)} f(w)/(w-z)\,dw$ is analytic in $z$ on
`Metric.ball z₀ r`, provided $f$ is analytic on the punctured ball `Metric.ball z₀ R \ {z₀}`
and $0 < r < R$.

The proof lifts `r` to `ℝ≥0`, establishes `CircleIntegrable f z₀ r` from the fact that the
sphere of radius `r` lies inside `Metric.ball z₀ R \ {z₀}`, then applies
`hasFPowerSeriesOn_cauchy_integral` to get a power series; `AnalyticOn.congr` rewrites the
smul-kernel to the `f w / (w - z)` form via `smul_eq_mul` and `div_eq_mul_inv`. -/
theorem analyticOn_cauchy_integral
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r : ℝ} (hr_pos : 0 < r) (hr_lt_R : r < R) :
    AnalyticOn ℂ (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
      ∮ w in C(z₀, r), f w / (w - z)) (Metric.ball z₀ r) := by
  have hci : CircleIntegrable f z₀ r := by
    apply ContinuousOn.circleIntegrable hr_pos.le
    apply hf.continuousOn.mono
    intro w hw
    rw [Metric.mem_sphere] at hw
    refine ⟨?_, ?_⟩
    · rw [Metric.mem_ball, hw]; exact hr_lt_R
    · intro hw_eq
      rw [Set.mem_singleton_iff] at hw_eq
      subst hw_eq
      simp [dist_self] at hw
      linarith
  lift r to NNReal using hr_pos.le with r'
  have hr'_pos : (0 : NNReal) < r' := by exact_mod_cast hr_pos
  have hpow := hasFPowerSeriesOn_cauchy_integral hci hr'_pos
  have han : AnalyticOnNhd ℂ
      (fun w => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ • ∮ z in C(z₀, ↑r'), (z - w)⁻¹ • f z)
      (Metric.eball z₀ ↑r') := hpow.analyticOnNhd
  rw [Metric.eball_coe] at han
  refine (han.analyticOn).congr ?_
  intro z _
  simp [smul_eq_mul, div_eq_mul_inv, mul_comm]

/-- For $z_1, z \in$ `Metric.ball z₀ R`, if `dist z z₀ < (dist z₁ z₀ + R) / 2`, then the
circle integrals with radii `(dist z z₀ + R) / 2` and `(dist z₁ z₀ + R) / 2` agree:
$\oint_{C(z_0,(d(z,z_0)+R)/2)} f(w)/(w-z) = \oint_{C(z_0,(d(z_1,z_0)+R)/2)} f(w)/(w-z)$.

This follows from `cauchy_kernel_circle_int_radius_indep` applied to the two midpoint radii. -/
theorem circleIntegral_eq_of_radius
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z₁ ∈ Metric.ball z₀ R, ∀ z ∈ Metric.ball z₀ R,
      dist z z₀ < (dist z₁ z₀ + R) / 2 →
      (∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z)) =
      (∮ w in C(z₀, (dist z₁ z₀ + R) / 2), f w / (w - z)) := by
  intro z₁ hz₁ z hz hdist
  rw [Metric.mem_ball] at hz₁ hz
  exact cauchy_kernel_circle_int_radius_indep hR hf z (Metric.mem_ball.mpr hz)
    ((dist z z₀ + R) / 2) ((dist z₁ z₀ + R) / 2)
    (by linarith) (by linarith) hdist (by linarith)

/-- For any $z_1 \in$ `Metric.ball z₀ R`, eventually in a neighborhood of $z_1$, every $z$
belongs to `Metric.ball z₀ R` and satisfies `dist z z₀ < (dist z₁ z₀ + R) / 2`.

This is the topological half of the local fixed-radius substitution: the midpoint radius
`(dist z₁ z₀ + R) / 2` dominates `dist z z₀` on a small ball around $z_1$. -/
theorem eventually_mem_ball_and_dist_lt
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (_hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z₁ ∈ Metric.ball z₀ R,
      ∀ᶠ z in nhds z₁,
        z ∈ Metric.ball z₀ R ∧ dist z z₀ < (dist z₁ z₀ + R) / 2 := by
  intro z₁ hz₁
  simp only [Metric.mem_ball] at hz₁
  have hr : 0 < (dist z₁ z₀ + R) / 2 - dist z₁ z₀ := by linarith
  filter_upwards [Metric.ball_mem_nhds z₁ hr] with z hz
  simp only [Metric.mem_ball] at hz
  exact ⟨Metric.mem_ball.mpr (by linarith [dist_triangle z z₁ z₀]),
         by linarith [dist_triangle z z₁ z₀]⟩

/-- For each $z_1 \in$ `Metric.ball z₀ R`, the variable-radius Cauchy kernel
$(2\pi i)^{-1}\oint_{C(z_0,(d(z,z_0)+R)/2)} f(w)/(w-z)$ is eventually equal (in a neighborhood
of $z_1$) to the fixed-radius version with radius $(d(z_1,z_0)+R)/2$.

The proof combines `eventually_mem_ball_and_dist_lt` (the topological neighborhood) with
`circleIntegral_eq_of_radius` (pointwise radius equality). -/
theorem cauchy_kernel_eventuallyEq
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z₁ ∈ Metric.ball z₀ R,
      (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        ∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z)) =ᶠ[nhds z₁]
      fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        ∮ w in C(z₀, (dist z₁ z₀ + R) / 2), f w / (w - z) := by
  intro z₁ hz₁
  have h_nbhd := eventually_mem_ball_and_dist_lt hR hf z₁ hz₁
  have h_eq := circleIntegral_eq_of_radius hR hf z₁ hz₁
  filter_upwards [h_nbhd] with z hz
  obtain ⟨hzball, hzd⟩ := hz
  exact congrArg ((2 * (Real.pi : ℂ) * Complex.I)⁻¹ * ·) (h_eq z hzball hzd)

/-- The variable-radius Cauchy kernel
$z \mapsto (2\pi i)^{-1}\oint_{C(z_0,(d(z,z_0)+R)/2)} f(w)/(w-z)$
is analytic on `Metric.ball z₀ R`, provided `f` is analytic on the punctured ball
`Metric.ball z₀ R \ {z₀}`.

At each $z_1$, the midpoint radius $r_1 := (d(z_1,z_0)+R)/2$ satisfies $z_1 \in$
`Metric.ball z₀ r₁`, so `analyticOn_cauchy_integral` yields analyticity of the fixed-radius
version; `cauchy_kernel_eventuallyEq` and `AnalyticAt.congr` transfer this to the
variable-radius kernel. -/
theorem analyticOn_cauchy_kernel
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    AnalyticOn ℂ
      (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        ∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z))
      (Metric.ball z₀ R) := by
  intro z₁ hz₁
  have hz₁_dist : dist z₁ z₀ < R := Metric.mem_ball.mp hz₁
  set r₁ := (dist z₁ z₀ + R) / 2 with hr₁_def
  have hd_nn : (0:ℝ) ≤ dist z₁ z₀ := dist_nonneg
  have hr₁_pos : 0 < r₁ := by simp [hr₁_def]; linarith
  have hr₁_lt_R : r₁ < R := by simp [hr₁_def]; linarith
  have hr₁_gt_dist : dist z₁ z₀ < r₁ := by simp [hr₁_def]; linarith
  have h_fixed := analyticOn_cauchy_integral hR hf hr₁_pos hr₁_lt_R
  have h_eq := cauchy_kernel_eventuallyEq hR hf z₁ hz₁
  have h_at : AnalyticAt ℂ (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
      ∮ w in C(z₀, r₁), f w / (w - z)) z₁ :=
    h_fixed.analyticAt (Metric.isOpen_ball.mem_nhds (Metric.mem_ball.mpr hr₁_gt_dist))
  exact ((h_at.congr h_eq.symm)).analyticWithinAt

/-- There exists an analytic function $g$ on `Metric.ball z₀ R` that agrees with the Cauchy
integral $(2\pi i)^{-1}\oint_{C(z_0,r)} f(w)/(w-z)$ for every $z$ in the ball and every
valid radius $r$ with `dist z z₀ < r < R`.

The witness is $g(z) = (2\pi i)^{-1}\oint_{C(z_0,(d(z,z_0)+R)/2)} f(w)/(w-z)$; analyticity
follows from `analyticOn_cauchy_kernel` and the radius-independence from
`cauchy_kernel_norm_circle_int_radius_indep`. -/
theorem exists_analyticOn_cauchy_kernel
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (g : ℂ → ℂ), AnalyticOn ℂ g (Metric.ball z₀ R) ∧
      ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
        g z = (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, r), f w / (w - z) := by
  refine ⟨fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z), ?_, ?_⟩
  · exact analyticOn_cauchy_kernel hR hf
  · intro z hz r hr_lo hr_hi
    exact cauchy_kernel_norm_circle_int_radius_indep hR hf z hz r hr_lo hr_hi

end Library.Analysis.ResidueTheorem.HolomorphicPart
