import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_outer_g_canonical_analytic_on_ball
import Problems.residue_thm.proofs.L_outer_g_canonical_eq_at_radius

namespace Problems.residue_thm

-- Outer holomorphic part `g(z) := (2πi)⁻¹ * ∮_{C(z₀, (dist z z₀ + R)/2)} f(w)/(w-z) dw`,
-- a canonical radius midway between `dist z z₀` and `R`. Two sub-goals:
--   * outer_g_canonical_analytic_on_ball: analyticity on `ball z₀ R` via locally agreeing
--     with the fixed-radius Cauchy integral (analytic by `hasFPowerSeriesOn_cauchy_integral`).
--   * outer_g_canonical_eq_at_radius: the formula at any other radius `r ∈ (dist z z₀, R)`
--     follows from radius-independence on the annulus where `w ↦ f(w)/(w-z)` is analytic.
theorem s10411
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (g : ℂ → ℂ), AnalyticOn ℂ g (Metric.ball z₀ R) ∧
      ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
        g z = (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, r), f w / (w - z)  := by
  refine ⟨fun z => (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, (dist z z₀ + R) / 2), f w / (w - z), ?_, ?_⟩
  · exact outer_g_canonical_analytic_on_ball hR hf
  · intro z hz r hr_lo hr_hi
    exact outer_g_canonical_eq_at_radius hR hf z hz r hr_lo hr_hi



end Problems.residue_thm
