import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10411

namespace Problems.residue_thm

-- outer_holomorphic_step_wrapper: alias for proved s10411 — constructs g analytic on ball z₀ R
-- equal to the Cauchy kernel integral at any valid interior radius.
theorem outer_holomorphic_step_wrapper
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) :
    ∃ (g : ℂ → ℂ), AnalyticOn ℂ g (Metric.ball z₀ R) ∧
      ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
        g z = (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
              ∮ w in C(z₀, r), f w / (w - z) := s10411 hR hf

end Problems.residue_thm
