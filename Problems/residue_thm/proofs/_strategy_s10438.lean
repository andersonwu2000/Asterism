import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_cocompact_decay_from_uniform
import Problems.residue_thm.proofs.L_uniform_bound_f_on_sphere

namespace Problems.residue_thm

-- Decompose the cocompact decay bound into (A) a uniform bound for ‖f‖ on the
-- sphere S(z₀, R/2) (analytic ⇒ continuous on compact set), and (B) the
-- length×sup circle-integral estimate that promotes this uniform bound to
-- a cocompact-eventually inequality.
-- Combine: obtain C from A, then feed C into B.
theorem s10438
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (P : ℂ → ℂ)
    (hP : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
        P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, ε), f w / (w - z))) :
    ∃ M : ℝ, 0 ≤ M ∧ ∀ᶠ z in Filter.cocompact ℂ,
      ‖∮ w in C(z₀, R/2), f w / (w - z)‖ ≤ M / (‖z - z₀‖ - R/2)  := by
  have h_bound := uniform_bound_f_on_sphere hR hf P hP
  obtain ⟨C, hC0, hC⟩ := h_bound
  exact cocompact_decay_from_uniform hR hf P hP C hC0 hC




end Problems.residue_thm
