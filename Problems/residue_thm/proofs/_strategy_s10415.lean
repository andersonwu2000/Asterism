import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_integrand_radius_indep

namespace Problems.residue_thm

-- Define P(z) using the canonical radius ε_c(z) = min R (dist z z₀) / 2; for
-- z ≠ z₀ this lies strictly between 0 and both R and dist z z₀, so it is a
-- valid integration radius. The sub-goal `integrand_radius_indep` (radius
-- independence of `∮ f w / (w - z) dw` over valid radii) then equates the
-- canonical integral with the integral at any other valid ε, closing the
-- existential equation. The sub-goal drops the outer ∃ binder and reduces the
-- witness construction to a pure equality between two circle integrals.
theorem s10415
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ P : ℂ → ℂ,
      ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))  := by
  refine ⟨fun z => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, min R (dist z z₀) / 2), f w / (w - z)), ?_⟩
  intro z hz ε hε hεd hεR
  have hd : 0 < dist z z₀ := dist_pos.mpr hz
  have hm_pos : 0 < min R (dist z z₀) := lt_min hR hd
  have hm_half_pos : 0 < min R (dist z z₀) / 2 := by linarith
  have hm_half_lt_d : min R (dist z z₀) / 2 < dist z z₀ := by
    have := min_le_right R (dist z z₀); linarith
  have hm_half_lt_R : min R (dist z z₀) / 2 < R := by
    have := min_le_left R (dist z z₀); linarith
  have hindep : (∮ w in C(z₀, min R (dist z z₀) / 2), f w / (w - z)) =
                (∮ w in C(z₀, ε), f w / (w - z)) :=
    integrand_radius_indep hR hf hz hm_half_pos hε
      hm_half_lt_d hεd hm_half_lt_R hεR
  simp only [hindep]

end Problems.residue_thm
