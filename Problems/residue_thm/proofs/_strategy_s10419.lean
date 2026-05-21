import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integral_tendsto_zero_at_cocompact

namespace Problems.residue_thm

-- Strip the outer `-((2πi)⁻¹ * ·)` wrapper: it's `Tendsto.const_mul` then `.neg`,
-- so the asymptotic core is just the circle integral going to 0 at cocompact.
-- Sub-goal carries all parent hypotheses and isolates the analytic content.
theorem s10419
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    Filter.Tendsto
      (fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, R/2), f w / (w - z)))
      (Filter.cocompact ℂ) (nhds 0)  := by
  have h_int := circle_integral_tendsto_zero_at_cocompact hR hf P hP
  have h_scaled := (h_int.const_mul ((2 * (Real.pi : ℂ) * Complex.I)⁻¹)).neg
  simpa using h_scaled
end Problems.residue_thm
