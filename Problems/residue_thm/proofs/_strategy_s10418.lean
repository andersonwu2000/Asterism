import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cauchy_kernel_diff_at_outside
import Problems.residue_thm.proofs.L_p_eventually_eq_cauchy_local

namespace Problems.residue_thm

-- Pointwise: every `z ∈ Set.univ \ {z₀}` gets `DifferentiableAt ℂ P z`, then
-- `.differentiableWithinAt`. Two sub-goals isolate the local rewrite from the
-- analytic core:
--   `p_eventually_eq_cauchy_local` — pick `ε` (smaller than `dist z z₀` and `R`),
--     shrink a neighborhood of `z` to keep `ζ ≠ z₀` and `dist ζ z₀ > ε`, then
--     apply `hP` pointwise to get `P =ᶠ[𝓝 z]` the Cauchy-kernel function.
--   `cauchy_kernel_diff_at_outside` — `ζ ↦ ∮ w in C(z₀, ε), f w / (w - ζ)` is
--     differentiable at `z` whenever `ε < dist z z₀` (parametric Leibniz; the
--     integrand is differentiable in `ζ` for every `w` on the circle).
-- Combinator: `Filter.EventuallyEq.differentiableAt_iff` transfers
-- `DifferentiableAt` from kernel to `P`.
theorem s10418
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    DifferentiableOn ℂ P (Set.univ \ {z₀})  := by
  intro z hz
  have hzne : z ≠ z₀ := fun h => hz.2 (h ▸ rfl)
  obtain ⟨ε, hε0, hεR, hεd, hPeq⟩ :=
    p_eventually_eq_cauchy_local hR hf P hP z hzne
  have h_diff :=
    cauchy_kernel_diff_at_outside hR hf ε hε0 hεR z hzne hεd
  exact ((hPeq.differentiableAt_iff).mpr h_diff).differentiableWithinAt

end Problems.residue_thm
