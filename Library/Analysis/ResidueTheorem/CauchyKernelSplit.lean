import Mathlib.Analysis.Complex.RemovableSingularity
import Library.Analysis.ResidueTheorem.CircleIntegralAnnulus

/-!
# Cauchy kernel splitting on annuli

This file establishes that the Cauchy kernel integral `∮ w in C(z₀, r), f w / (w - z)` is
independent of the radius `r`, provided `f` is analytic on a punctured ball
`Metric.ball z₀ R \ {z₀}` and `z` lies inside the circle of integration.  The key result is
`annulus_residue_diff`, which evaluates the difference of two such integrals at radii `r` (outer)
and `ε` (inner, with `ε < dist z z₀`) as `2 * π * I * f z`.

## Main statements

- `cauchy_kernel_cont_on_annulus`: the Cauchy kernel `f w / (w - z')` is continuous on every
  closed annulus contained in the punctured ball, as long as `z'` lies strictly inside the inner
  circle.
- `cauchy_kernel_diff_at_open_annulus`: the Cauchy kernel is complex-differentiable at every
  interior point of such an annulus.
- `cauchy_kernel_circle_int_radius_indep`: the circle integral of the Cauchy kernel is the same
  for any two radii between `dist z' z₀` and `R`.
- `cauchy_kernel_diff_outer_inner`: the difference of the pure inverse-kernel integrals at outer
  radius `r` and inner radius `ε` equals `2 * π * I`.
- `slope_integral_diff_radius_indep`: the difference of the divided-difference integrals
  `∮ (f w - f z) / (w - z)` at two radii vanishes.
- `annulus_residue_diff`: combining the above, the difference of the full Cauchy kernel integrals
  at radii `r` and `ε` equals `2 * π * I * f z`.
-/

open Library.Analysis.ResidueTheorem.CircleIntegralAnnulus

namespace Library.Analysis.ResidueTheorem.CauchyKernelSplit

/-- The Cauchy kernel `fun w => f w / (w - z')` is continuous on the closed annulus
`Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁`, provided `f` is analytic on the punctured ball
`Metric.ball z₀ R \ {z₀}`, and `z'` satisfies `dist z' z₀ < r₁ ≤ r₂ < R`. -/
theorem cauchy_kernel_cont_on_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z' ∈ Metric.ball z₀ R, ∀ r₁ r₂ : ℝ,
      dist z' z₀ < r₁ → r₁ ≤ r₂ → r₂ < R →
      ContinuousOn (fun w => f w / (w - z'))
        (Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁) := by
  intro z' hz' r₁ r₂ hr₁ hr₁r₂ hr₂
  apply ContinuousOn.div
  · apply hf.continuousOn.mono
    intro w hw
    simp only [Set.mem_diff, Metric.mem_closedBall, Metric.mem_ball,
               Set.mem_singleton_iff] at hw ⊢
    refine ⟨lt_of_le_of_lt hw.1 hr₂, ?_⟩
    intro heq
    subst heq
    simp only [dist_self] at hw
    linarith [dist_nonneg (x := z') (y := w), hw.2]
  · exact continuousOn_id.sub continuousOn_const
  · intro w hw
    simp only [Set.mem_diff, Metric.mem_closedBall, Metric.mem_ball] at hw
    have hdist : r₁ ≤ dist w z₀ := not_lt.mp hw.2
    simp only [sub_ne_zero]
    intro heq
    rw [heq] at hdist
    linarith

/-- The Cauchy kernel `fun w => f w / (w - z')` is complex-differentiable at every point of
the open annulus `Metric.ball z₀ r₂ \ Metric.closedBall z₀ r₁`, provided `f` is analytic on
`Metric.ball z₀ R \ {z₀}` and `z'` satisfies `dist z' z₀ < r₁`.  The key point is that `z ≠ z'`
follows from the distance assumptions, so the pole at `z'` is avoided. -/
theorem cauchy_kernel_diff_at_open_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z' ∈ Metric.ball z₀ R, ∀ r₁ r₂ : ℝ,
      dist z' z₀ < r₁ → r₁ ≤ r₂ → r₂ < R →
      ∀ z ∈ Metric.ball z₀ r₂ \ Metric.closedBall z₀ r₁,
        DifferentiableAt ℂ (fun w => f w / (w - z')) z := by
  intro z' _hz' r₁ r₂ hr₁z' hr₁r₂ hr₂R z hz
  simp only [Set.mem_diff, Metric.mem_ball, Metric.mem_closedBall, not_le] at hz
  obtain ⟨hzr₂, hzr₁⟩ := hz
  have hzR : z ∈ Metric.ball z₀ R := Metric.mem_ball.mpr (hzr₂.trans hr₂R)
  have hr₁_pos : 0 < r₁ := lt_of_le_of_lt dist_nonneg hr₁z'
  have hzz₀ : z ≠ z₀ := by
    intro h; subst h; simp [dist_self] at hzr₁; linarith
  have hzz' : z ≠ z' := by
    intro h; subst h; linarith
  have hmem : z ∈ Metric.ball z₀ R \ ({z₀} : Set ℂ) :=
    ⟨hzR, by rintro (rfl : z = z₀); exact hzz₀ rfl⟩
  have hopen : IsOpen (Metric.ball z₀ R \ ({z₀} : Set ℂ)) :=
    Metric.isOpen_ball.sdiff isClosed_singleton
  have hfz : DifferentiableAt ℂ f z :=
    (hf.analyticAt (hopen.mem_nhds hmem)).differentiableAt
  exact hfz.div (DifferentiableAt.sub differentiableAt_id (differentiableAt_const z'))
    (sub_ne_zero.mpr hzz')

/-- The circle integral `∮ w in C(z₀, r), f w / (w - z')` is independent of the radius `r`,
provided `dist z' z₀ < r < R` and `f` is analytic on `Metric.ball z₀ R \ {z₀}`.  This follows
from `Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable` applied to the Cauchy
kernel, which is continuous on annuli and holomorphic on their interiors. -/
theorem cauchy_kernel_circle_int_radius_indep
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z' ∈ Metric.ball z₀ R, ∀ r₁ r₂ : ℝ,
      dist z' z₀ < r₁ → r₁ < R → dist z' z₀ < r₂ → r₂ < R →
      (∮ w in C(z₀, r₁), f w / (w - z')) = (∮ w in C(z₀, r₂), f w / (w - z')) := by
  intro z' hz' r₁ r₂ hd₁ hr₁R hd₂ hr₂R
  have hr₁p : 0 < r₁ := lt_of_le_of_lt dist_nonneg hd₁
  have hr₂p : 0 < r₂ := lt_of_le_of_lt dist_nonneg hd₂
  have h_cont := cauchy_kernel_cont_on_annulus hR hf
  have h_diff := cauchy_kernel_diff_at_open_annulus hR hf
  rcases le_total r₁ r₂ with hle | hle
  · have h_c := h_cont z' hz' r₁ r₂ hd₁ hle hr₂R
    have h_d := h_diff z' hz' r₁ r₂ hd₁ hle hr₂R
    exact (Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable hr₁p hle
      Set.countable_empty h_c (fun z hz => h_d z hz.1)).symm
  · have h_c := h_cont z' hz' r₂ r₁ hd₂ hle hr₁R
    have h_d := h_diff z' hz' r₂ r₁ hd₂ hle hr₁R
    exact Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable hr₂p hle
      Set.countable_empty h_c (fun z hz => h_d z hz.1)

/-- The circle integral of the Cauchy kernel is unchanged when the radius is replaced by the
midpoint `(dist z z₀ + R) / 2`.  This is a normalised form of
`cauchy_kernel_circle_int_radius_indep` used to pin a canonical representative for the Cauchy
integral. -/
theorem cauchy_kernel_norm_circle_int_radius_indep
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
      (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        (∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z)) =
      (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        (∮ w in C(z₀, r), f w / (w - z)) := by
  intro z hz r hzr hrR
  have hzlt_R : dist z z₀ < R := Metric.mem_ball.mp hz
  have hmid_lo : dist z z₀ < (dist z z₀ + R) / 2 := by linarith
  have hmid_hi : (dist z z₀ + R) / 2 < R := by linarith
  have h_indep := cauchy_kernel_circle_int_radius_indep hR hf
  have h := h_indep z hz ((dist z z₀ + R) / 2) r hmid_lo hmid_hi hzr hrR
  rw [h]

/-- The difference of the pure inverse-kernel circle integrals at outer radius `r` and inner
radius `ε` (with `ε < dist z z₀ < r`) equals `2 * π * I`.  The outer integral equals `2 * π * I`
by the Cauchy integral formula for `(w - z)⁻¹`; the inner integral vanishes because `z` lies
outside the closed ball of radius `ε`, so `(w - z)⁻¹` is holomorphic there. -/
theorem cauchy_kernel_diff_outer_inner
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (_hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (_hzB : z ∈ Metric.ball z₀ R) (_hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (_hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹)
      = 2 * (Real.pi : ℂ) * Complex.I := by
  have hz_in_r : z ∈ Metric.ball z₀ r := Metric.mem_ball.mpr hr_lb
  have outer : (∮ w in C(z₀, r), (w - z)⁻¹) = 2 * ↑Real.pi * Complex.I :=
    circleIntegral.integral_sub_inv_of_mem_ball hz_in_r
  have hz_not_in_closed_eps : ∀ w ∈ Metric.closedBall z₀ ε, w ≠ z := fun w hw heq => by
    rw [← heq] at hε_lt_d
    exact absurd (Metric.mem_closedBall.mp hw) (not_le.mpr hε_lt_d)
  have inner : (∮ w in C(z₀, ε), (w - z)⁻¹) = 0 := by
    apply DiffContOnCl.circleIntegral_eq_zero hε_pos.le
    constructor
    · intro w hw
      apply DifferentiableAt.differentiableWithinAt
      exact (differentiableAt_id.sub_const z).inv
        (sub_ne_zero.mpr (hz_not_in_closed_eps w (Metric.ball_subset_closedBall hw)))
    · apply ContinuousOn.mono
        ((continuousOn_id.sub continuousOn_const).inv₀
          (fun w hw => sub_ne_zero.mpr (hz_not_in_closed_eps w hw)))
      exact Metric.closure_ball_subset_closedBall
  rw [outer, inner, sub_zero]

/-- Pointwise identity: for `w` on the sphere `Metric.sphere z₀ ρ` and `z` off the sphere,
`f w / (w - z) = f z * (w - z)⁻¹ + (f w - f z) / (w - z)`. -/
theorem kernel_split_pointwise
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (_hρ : 0 < ρ)
    (_hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (_hz : z ∉ Metric.sphere z₀ ρ) :
    ∀ w ∈ Metric.sphere z₀ ρ,
      f w / (w - z) = f z * (w - z)⁻¹ + (f w - f z) / (w - z) := by grind

/-- The function `fun w => f z * (w - z)⁻¹` is circle-integrable on `C(z₀, ρ)` when
`z ∉ Metric.sphere z₀ ρ`, because `(w - z)⁻¹` is continuous on the sphere (the pole at `z` lies
off the sphere) and the prefactor `f z` is constant. -/
theorem circle_integrable_const_mul_inv
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (hρ : 0 < ρ)
    (_hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (hz : z ∉ Metric.sphere z₀ ρ) :
    CircleIntegrable (fun w => f z * (w - z)⁻¹) z₀ ρ := by
  apply ContinuousOn.circleIntegrable hρ.le
  apply ContinuousOn.mul continuousOn_const
  apply (continuousOn_id.sub continuousOn_const).inv₀
  intro w hw h
  exact hz (sub_eq_zero.mp h ▸ hw)

/-- The function `fun w => (f w - f z) / (w - z)` is circle-integrable on `C(z₀, ρ)` when
`f` is continuous on the sphere and `z ∉ Metric.sphere z₀ ρ`. -/
theorem circle_integrable_diff_div
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (hρ : 0 < ρ)
    (hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (hz : z ∉ Metric.sphere z₀ ρ) :
    CircleIntegrable (fun w => (f w - f z) / (w - z)) z₀ ρ := by
  apply ContinuousOn.circleIntegrable hρ.le
  apply ContinuousOn.div
  · exact hfcont.sub continuousOn_const
  · exact (continuous_id.sub continuous_const).continuousOn
  · intro w hw
    exact sub_ne_zero.mpr (fun heq => hz (heq ▸ hw))

/-- The circle integral of the Cauchy kernel splits linearly as
`∮ w in C(z₀, ρ), f w / (w - z)`
`= f z * ∮ w in C(z₀, ρ), (w - z)⁻¹ + ∮ w in C(z₀, ρ), (f w - f z) / (w - z)`.
This follows by applying the pointwise identity `kernel_split_pointwise` and lifting via
`circleIntegral.integral_add` and `circleIntegral.integral_const_mul`. -/
theorem circle_kernel_linear_split
    {f : ℂ → ℂ} {z₀ z : ℂ} {ρ : ℝ}
    (hρ : 0 < ρ)
    (hfcont : ContinuousOn f (Metric.sphere z₀ ρ))
    (hz : z ∉ Metric.sphere z₀ ρ) :
    (∮ w in C(z₀, ρ), f w / (w - z))
      = f z * (∮ w in C(z₀, ρ), (w - z)⁻¹)
        + (∮ w in C(z₀, ρ), (f w - f z) / (w - z)) := by
  have h_pointwise := kernel_split_pointwise hρ hfcont hz
  have h_int_const_mul_inv := circle_integrable_const_mul_inv hρ hfcont hz
  have h_int_diff_div := circle_integrable_diff_div hρ hfcont hz
  have h_eq : (∮ w in C(z₀, ρ), f w / (w - z))
      = (∮ w in C(z₀, ρ), f z * (w - z)⁻¹ + (f w - f z) / (w - z)) :=
    circleIntegral.integral_congr hρ.le h_pointwise
  rw [h_eq, circleIntegral.integral_add h_int_const_mul_inv h_int_diff_div,
      circleIntegral.integral_const_mul]

/-- The difference of the full Cauchy kernel integrals at radii `r` and `ε` splits as
`f z` times the difference of inverse-kernel integrals plus the difference of divided-difference
integrals.  Both circles avoid the pole at `z` (since `ε < dist z z₀ < r`), enabling the
pointwise linear splitting via `circle_kernel_linear_split`. -/
theorem kernel_integral_linear_split
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hzB : z ∈ Metric.ball z₀ R) (_hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), f w / (w - z))
      - (∮ w in C(z₀, ε), f w / (w - z))
      = f z * ((∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹))
        + ((∮ w in C(z₀, r), (f w - f z) / (w - z))
            - (∮ w in C(z₀, ε), (f w - f z) / (w - z))) := by
  have hr_pos : 0 < r := dist_nonneg.trans_lt hr_lb
  have hd_lt_R : dist z z₀ < R := Metric.mem_ball.mp hzB
  have hε_lt_R : ε < R := hε_lt_d.trans hd_lt_R
  have hcontR : ContinuousOn f (Metric.sphere z₀ r) := by
    apply hf.continuousOn.mono
    intro w hw
    rw [Metric.mem_sphere] at hw
    refine ⟨Metric.mem_ball.mpr (by rw [hw]; exact hr_ub), ?_⟩
    intro hw_eq
    rw [Set.mem_singleton_iff] at hw_eq
    rw [hw_eq, dist_self] at hw
    exact hr_pos.ne hw
  have hcontε : ContinuousOn f (Metric.sphere z₀ ε) := by
    apply hf.continuousOn.mono
    intro w hw
    rw [Metric.mem_sphere] at hw
    refine ⟨Metric.mem_ball.mpr (by rw [hw]; exact hε_lt_R), ?_⟩
    intro hw_eq
    rw [Set.mem_singleton_iff] at hw_eq
    rw [hw_eq, dist_self] at hw
    exact hε_pos.ne hw
  have hzNotr : z ∉ Metric.sphere z₀ r := by
    rw [Metric.mem_sphere]; exact hr_lb.ne
  have hzNotε : z ∉ Metric.sphere z₀ ε := by
    rw [Metric.mem_sphere]; exact hε_lt_d.ne'
  have h_outer := circle_kernel_linear_split (f := f) (z₀ := z₀) (z := z)
      hr_pos hcontR hzNotr
  have h_inner := circle_kernel_linear_split (f := f) (z₀ := z₀) (z := z)
      hε_pos hcontε hzNotε
  rw [h_outer, h_inner]; ring

/-- The difference of the divided-difference integrals
`∮ w in C(z₀, r), (f w - f z) / (w - z)` and `∮ w in C(z₀, ε), (f w - f z) / (w - z)` is zero.
The key observation is that `(f v - f z) / (v - z) = dslope f z v` for `v ≠ z`, and
`dslope f z` is analytic on `Metric.ball z₀ R \ {z₀}` by `Complex.differentiableOn_dslope`.
Radius independence then follows from `circle_integral_radius_indep_on_punctured_ball`. -/
theorem slope_integral_diff_radius_indep
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (_hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hzB : z ∈ Metric.ball z₀ R) (hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), (f w - f z) / (w - z))
      - (∮ w in C(z₀, ε), (f w - f z) / (w - z)) = 0 := by
  have hzB' : z ∈ Metric.ball z₀ R \ {z₀} := by
    simp only [Set.mem_diff, Set.mem_singleton_iff]; exact ⟨hzB, hzNe⟩
  have hopen : IsOpen (Metric.ball z₀ R \ {z₀}) :=
    Metric.isOpen_ball.sdiff isClosed_singleton
  have hdist_pos : 0 < dist z z₀ := dist_pos.mpr hzNe
  have hr_pos : 0 < r := lt_trans hdist_pos hr_lb
  have handslope : AnalyticOn ℂ (dslope f z) (Metric.ball z₀ R \ {z₀}) :=
    ((Complex.differentiableOn_dslope (hopen.mem_nhds hzB')).mpr
      hf.differentiableOn).analyticOn hopen
  have slope_eq : ∀ v : ℂ, v ≠ z →
      (f v - f z) / (v - z) = dslope f z v := fun v hvz => by
    simp only [dslope_of_ne _ hvz, slope, smul_eq_mul, vsub_eq_sub,
               div_eq_mul_inv, mul_comm]
  have heq_r : (∮ v in C(z₀, r), (f v - f z) / (v - z)) =
               ∮ v in C(z₀, r), dslope f z v :=
    circleIntegral.integral_congr hr_pos.le fun v hv => by
      rw [Metric.mem_sphere] at hv
      exact slope_eq v (fun heq => by rw [heq] at hv; linarith [dist_comm z₀ z])
  have heq_ε : (∮ v in C(z₀, ε), (f v - f z) / (v - z)) =
               ∮ v in C(z₀, ε), dslope f z v :=
    circleIntegral.integral_congr hε_pos.le fun v hv => by
      rw [Metric.mem_sphere] at hv
      exact slope_eq v (fun heq => by rw [heq] at hv; linarith [dist_comm z₀ z])
  rw [heq_r, heq_ε]
  exact sub_eq_zero.mpr
    (circle_integral_radius_indep_on_punctured_ball handslope hε_pos
      (le_of_lt (lt_trans hε_lt_d hr_lb)) hr_ub).symm

/-- **Annulus residue formula**: the difference of the Cauchy kernel circle integrals at outer
radius `r` and inner radius `ε` (with `ε < dist z z₀ < r < R`) equals `2 * π * I * f z`.
This is obtained by combining `kernel_integral_linear_split`, `cauchy_kernel_diff_outer_inner`
(which computes the inverse-kernel difference as `2 * π * I`), and
`slope_integral_diff_radius_indep` (which shows the divided-difference part vanishes). -/
theorem annulus_residue_diff
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hzB : z ∈ Metric.ball z₀ R) (hzNe : z ≠ z₀)
    {r : ℝ} (hr_lb : dist z z₀ < r) (hr_ub : r < R)
    {ε : ℝ} (hε_pos : 0 < ε) (hε_lt_d : ε < dist z z₀) :
    (∮ w in C(z₀, r), f w / (w - z))
      - (∮ w in C(z₀, ε), f w / (w - z))
      = 2 * (Real.pi : ℂ) * Complex.I * f z := by
  have h_ker :
      (∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹)
        = 2 * (Real.pi : ℂ) * Complex.I :=
    cauchy_kernel_diff_outer_inner hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  have h_slp :
      (∮ w in C(z₀, r), (f w - f z) / (w - z))
        - (∮ w in C(z₀, ε), (f w - f z) / (w - z)) = 0 :=
    slope_integral_diff_radius_indep hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  have h_spl :
      (∮ w in C(z₀, r), f w / (w - z))
        - (∮ w in C(z₀, ε), f w / (w - z))
      = f z * ((∮ w in C(z₀, r), (w - z)⁻¹) - (∮ w in C(z₀, ε), (w - z)⁻¹))
        + ((∮ w in C(z₀, r), (f w - f z) / (w - z))
            - (∮ w in C(z₀, ε), (f w - f z) / (w - z))) :=
    kernel_integral_linear_split hR hf hzB hzNe hr_lb hr_ub hε_pos hε_lt_d
  rw [h_spl, h_ker, h_slp]
  ring

end Library.Analysis.ResidueTheorem.CauchyKernelSplit
