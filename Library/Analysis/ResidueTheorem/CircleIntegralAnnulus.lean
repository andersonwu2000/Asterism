import Mathlib.Analysis.CStarAlgebra.Classes
import Mathlib.Analysis.Complex.CauchyIntegral

/-!
# Circle integrals on annuli and the residue theorem

This file develops the key analytic lemmas showing that circle integrals of a function
with an isolated singularity are independent of the radius, then uses this to give a
formula for `Complex.residue` in terms of a circle integral at any sufficiently small
positive radius.

## Main statements

- `continuous_on_closed_annulus`: a function analytic on a punctured ball
  `Metric.ball z₀ R \ {z₀}` is continuous on every closed annulus contained in that set.
- `differentiable_at_open_annulus`: the same function is complex-differentiable at every
  point of the corresponding open annulus.
- `circle_integral_radius_indep_on_punctured_ball`: the circle integral
  `∮ z in C(z₀, r), f z` is independent of `r`, for `r` ranging over the analytic
  punctured ball.
- `circle_integral_eq_two_radii`: circle integrals at radii drawn from two (possibly
  different) analytic punctured balls for the same singularity coincide.
- `residue_eq_circle_integral`: `Complex.residue f z₀ = (1 / (2πi)) * ∮ z in C(z₀, r), f z`
  for any `r` in the analytic punctured ball.
-/

namespace Complex

open Classical in
/--
Residue of `f` at the isolated singularity `z₀`.

When `f` is analytic on a punctured ball `Metric.ball z₀ R \ {z₀}` for
some `R > 0`, define `residue f z₀ := (1/(2πi)) · ∮ z in C(z₀, R/2), f z`
for one such `R` chosen classically. Independence from the chosen `R`
follows from contour deformation on the annulus.

Outside the regime (no positive analytic radius exists), residue = 0.
-/
noncomputable def residue (f : ℂ → ℂ) (z₀ : ℂ) : ℂ :=
  if h : ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}) then
    (1 / (2 * Real.pi * Complex.I)) *
      ∮ z in C(z₀, Classical.choose h / 2), f z
  else 0

end Complex

namespace Library.Analysis.ResidueTheorem.CircleIntegralAnnulus

/-- A function analytic on the punctured ball `Metric.ball z₀ R \ {z₀}` is continuous on
every closed annulus `Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁` with `0 < r₁ ≤ r₂ < R`.
The proof restricts the continuity provided by `AnalyticOn.continuousOn` to the annulus,
which lies in `Metric.ball z₀ R \ {z₀}` because the inner ball excludes `z₀`. -/
theorem continuous_on_closed_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r₁ r₂ : ℝ} (hr₁ : 0 < r₁) (_hle : r₁ ≤ r₂) (hr₂ : r₂ < R) :
    ContinuousOn f (Metric.closedBall z₀ r₂ \ Metric.ball z₀ r₁) := by
  apply hf.continuousOn.mono
  intro x ⟨hx1, hx2⟩
  simp only [Set.mem_diff, Metric.mem_ball, Set.mem_singleton_iff]
  refine ⟨lt_of_le_of_lt (Metric.mem_closedBall.mp hx1) hr₂, ?_⟩
  intro heq
  apply hx2
  rw [Metric.mem_ball, heq, dist_self]
  exact hr₁

/-- A function analytic on the punctured ball `Metric.ball z₀ R \ {z₀}` is complex-differentiable
at every point of the open annulus `Metric.ball z₀ r₂ \ Metric.closedBall z₀ r₁`
with `0 < r₁ ≤ r₂ < R`. -/
theorem differentiable_at_open_annulus
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r₁ r₂ : ℝ} (hr₁ : 0 < r₁) (_hle : r₁ ≤ r₂) (hr₂ : r₂ < R) :
    ∀ z ∈ Metric.ball z₀ r₂ \ Metric.closedBall z₀ r₁, DifferentiableAt ℂ f z := by
  intro z hz
  have hzR : z ∈ Metric.ball z₀ R := Metric.ball_subset_ball hr₂.le hz.1
  have hzne : z ∉ ({z₀} : Set ℂ) := by
    simp only [Set.mem_singleton_iff]
    intro h
    exact hz.2 (h ▸ Metric.mem_closedBall_self hr₁.le)
  have hmem : z ∈ Metric.ball z₀ R \ {z₀} := ⟨hzR, hzne⟩
  have hopen : IsOpen (Metric.ball z₀ R \ {z₀}) :=
    IsOpen.sdiff Metric.isOpen_ball isClosed_singleton
  exact hf.differentiableOn.differentiableAt (hopen.mem_nhds hmem)

/-- The circle integral `∮ z in C(z₀, r), f z` of a function analytic on the punctured ball
`Metric.ball z₀ R \ {z₀}` is independent of the radius `r`, for any `0 < r₁ ≤ r₂ < R`.
This follows from `Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable`
applied to the annulus between `r₁` and `r₂`. -/
theorem circle_integral_radius_indep_on_punctured_ball
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r₁ r₂ : ℝ} (hr₁ : 0 < r₁) (hle : r₁ ≤ r₂) (hr₂ : r₂ < R) :
    (∮ z in C(z₀, r₁), f z) = (∮ z in C(z₀, r₂), f z) := by
  exact (Complex.circleIntegral_eq_of_differentiable_on_annulus_off_countable hr₁ hle
      Set.countable_empty (continuous_on_closed_annulus hf hr₁ hle hr₂)
      (fun z hz => differentiable_at_open_annulus hf hr₁ hle hr₂ z hz.1)).symm

/-- If `f` is analytic on `Metric.ball z₀ R₁ \ {z₀}` and on `Metric.ball z₀ R₂ \ {z₀}`,
then the circle integrals at any radii `r₁ < R₁` and `r₂ < R₂` are equal.
The proof introduces an intermediate radius `ρ = min r₁ r₂ / 2` lying inside both
analytic punctured balls, then applies `circle_integral_radius_indep_on_punctured_ball`
from each side. -/
theorem circle_integral_eq_two_radii
    {f : ℂ → ℂ} {z₀ : ℂ} {R₁ R₂ : ℝ}
    (hf₁ : AnalyticOn ℂ f (Metric.ball z₀ R₁ \ {z₀}))
    (hf₂ : AnalyticOn ℂ f (Metric.ball z₀ R₂ \ {z₀}))
    {r₁ : ℝ} (hr₁ : 0 < r₁) (hr₁R₁ : r₁ < R₁)
    {r₂ : ℝ} (hr₂ : 0 < r₂) (hr₂R₂ : r₂ < R₂) :
    (∮ z in C(z₀, r₁), f z) = (∮ z in C(z₀, r₂), f z) := by
  set ρ := min r₁ r₂ / 2 with hρ_def
  have hρ_pos : 0 < ρ := by positivity
  have hρr₁ : ρ ≤ r₁ := by
    simp [hρ_def]
    linarith [min_le_left r₁ r₂]
  have hρr₂ : ρ ≤ r₂ := by
    simp [hρ_def]
    linarith [min_le_right r₁ r₂]
  have h1 : (∮ z in C(z₀, ρ), f z) = (∮ z in C(z₀, r₁), f z) :=
    circle_integral_radius_indep_on_punctured_ball hf₁ hρ_pos hρr₁ hr₁R₁
  have h2 : (∮ z in C(z₀, ρ), f z) = (∮ z in C(z₀, r₂), f z) :=
    circle_integral_radius_indep_on_punctured_ball hf₂ hρ_pos hρr₂ hr₂R₂
  exact h1.symm.trans h2

/-- `Complex.residue f z₀` equals the circle integral formula at any admissible radius.
If `f` is analytic on `Metric.ball z₀ R \ {z₀}` and `0 < r < R`, then
`Complex.residue f z₀ = (1 / (2 * π * I)) * ∮ z in C(z₀, r), f z`.
The proof unfolds the classical choice in the definition of `Complex.residue` and
uses `circle_integral_eq_two_radii` to bridge between the chosen radius and `r`. -/
theorem residue_eq_circle_integral
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ}
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {r : ℝ} (hr : 0 < r) (hrR : r < R) :
    Complex.residue f z₀ =
      (1 / (2 * Real.pi * Complex.I)) * ∮ z in C(z₀, r), f z := by
  have hex : ∃ R' : ℝ, 0 < R' ∧ AnalyticOn ℂ f (Metric.ball z₀ R' \ {z₀}) :=
    ⟨R, lt_trans hr hrR, hf⟩
  obtain ⟨hR'_pos, hf'⟩ := Classical.choose_spec hex
  have h_bridge : (∮ z in C(z₀, Classical.choose hex / 2), f z) = (∮ z in C(z₀, r), f z) :=
    circle_integral_eq_two_radii hf' hf (half_pos hR'_pos) (half_lt_self hR'_pos) hr hrR
  unfold Complex.residue
  rw [dif_pos hex, h_bridge]

end Library.Analysis.ResidueTheorem.CircleIntegralAnnulus
