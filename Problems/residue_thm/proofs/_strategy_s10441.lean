import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cocompact_eventually_far_from_z0
import Problems.residue_thm.proofs.L_pointwise_circle_int_div_bound

namespace Problems.residue_thm

-- Pick M := 2 * π * (R/2) * C and split into:
-- (A) Cocompact-eventual far-field: R/2 < ‖z - z₀‖ eventually as z escapes compacts.
-- (B) Pointwise length×sup bound: at any z with R/2 < ‖z - z₀‖, the circle integral
--     ‖∮ w in C(z₀, R/2), f w / (w - z)‖ is bounded by M / (‖z - z₀‖ - R/2)
--     (reverse triangle on the sphere gives ‖w - z‖ ≥ ‖z - z₀‖ - R/2 > 0, so
--     ‖f w / (w - z)‖ ≤ C / (‖z - z₀‖ - R/2); circle length 2π·(R/2) finishes).
theorem s10441
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z)))
    (C : ℝ) (hC0 : 0 ≤ C)
    (hC : ∀ w ∈ Metric.sphere z₀ (R/2), ‖f w‖ ≤ C) :
    ∃ M : ℝ, 0 ≤ M ∧ ∀ᶠ z in Filter.cocompact ℂ,
      ‖∮ w in C(z₀, R/2), f w / (w - z)‖ ≤ M / (‖z - z₀‖ - R/2)  := by
  refine ⟨2 * Real.pi * (R/2) * C, ?_, ?_⟩
  · have hpi : 0 ≤ Real.pi := Real.pi_pos.le
    have hRh : 0 ≤ R/2 := by linarith
    positivity
  · have h_far := cocompact_eventually_far_from_z0 hR hf P hP C hC0 hC
    have h_bd := pointwise_circle_int_div_bound hR hf P hP C hC0 hC
    filter_upwards [h_far] with z hz
    exact h_bd z hz


end Problems.residue_thm

