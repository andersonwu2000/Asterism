import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_integral_fixed_radius_analytic_on
import Problems.residue_thm.proofs.L_outer_g_local_radius_equality

namespace Problems.residue_thm

-- Pointwise analyticity via a local fixed-radius substitution.
-- At each z₁ ∈ ball z₀ R, set r₁ := (dist z₁ z₀ + R) / 2.
-- Sub-goal `cauchy_integral_fixed_radius_analytic_on`: fixed-radius Cauchy integral
-- is analytic on `ball z₀ r₁` (standard `hasFPowerSeriesOn_cauchy_integral`).
-- Sub-goal `outer_g_local_radius_equality`: near z₁, the variable-radius integrand
-- agrees with the fixed-radius one (radius-independence on the two-puncture annulus).
-- Combinator: `AnalyticOn.analyticAt` on the fixed-radius lemma + `AnalyticAt.congr`
-- with the eventual equality, then `AnalyticAt.analyticWithinAt` to land in `AnalyticOn`.
theorem s10416
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    AnalyticOn ℂ
      (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
        ∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z))
      (Metric.ball z₀ R)  := by
  intro z₁ hz₁
  have hz₁_dist : dist z₁ z₀ < R := Metric.mem_ball.mp hz₁
  set r₁ := (dist z₁ z₀ + R) / 2 with hr₁_def
  have hd_nn : (0:ℝ) ≤ dist z₁ z₀ := dist_nonneg
  have hr₁_pos : 0 < r₁ := by simp [hr₁_def]; linarith
  have hr₁_lt_R : r₁ < R := by simp [hr₁_def]; linarith
  have hr₁_gt_dist : dist z₁ z₀ < r₁ := by simp [hr₁_def]; linarith
  have h_fixed := cauchy_integral_fixed_radius_analytic_on hR hf hr₁_pos hr₁_lt_R
  have h_eq := outer_g_local_radius_equality hR hf z₁ hz₁
  have h_at : AnalyticAt ℂ (fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
      ∮ w in C(z₀, r₁), f w / (w - z)) z₁ :=
    h_fixed.analyticAt (Metric.isOpen_ball.mem_nhds (Metric.mem_ball.mpr hr₁_gt_dist))
  exact ((h_at.congr h_eq.symm)).analyticWithinAt

end Problems.residue_thm
