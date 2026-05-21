import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_int_param_diff_outside_at

namespace Problems.residue_thm

-- Reduce to differentiability of the bare circle-integral parameter map
-- `ζ ↦ ∮ w in C(z₀, ε), g w / (w - ζ)` at points `ζ` strictly outside the
-- circle. The `-((2πi)⁻¹ * _)` outer wrap is closed by `.const_mul.neg`.
--   `circle_int_param_diff_outside_at` — abstract sub-goal: parametric
--     Leibniz for a continuous integrand `g` on the sphere, evaluated at any
--     point at distance > r from the center.
-- Continuity of `f` on `sphere z₀ ε` is supplied inline from `hf.continuousOn`
-- restricted along `sphere z₀ ε ⊆ Metric.ball z₀ R \ {z₀}`.
theorem s10437
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (ε : ℝ) (hε0 : 0 < ε) (hεR : ε < R)
    (z : ℂ) (hzne : z ≠ z₀) (hεd : ε < dist z z₀) :
    DifferentiableAt ℂ
      (fun ζ => -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, ε), f w / (w - ζ))) z  := by
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

end Problems.residue_thm
