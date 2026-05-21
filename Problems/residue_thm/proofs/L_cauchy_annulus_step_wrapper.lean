import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10410

namespace Problems.residue_thm

-- cauchy_annulus_step_wrapper: f = g + P on punctured ball via annular Cauchy (alias s10410)

theorem cauchy_annulus_step_wrapper
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    (g P : ℂ → ℂ)
    (hg_eq : ∀ z, z ∈ Metric.ball z₀ R → ∀ r : ℝ, dist z z₀ < r → r < R →
      g z = (2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, r), f w / (w - z))
    (hP_eq : ∀ z, z ≠ z₀ → ∀ ε : ℝ, 0 < ε → ε < dist z z₀ → ε < R →
      P z = -((2 * (Real.pi : ℂ) * Complex.I)⁻¹ *
            ∮ w in C(z₀, ε), f w / (w - z))) :
    ∀ z ∈ Metric.ball z₀ R \ {z₀}, f z = g z + P z := by
  exact s10410 hR hf g P hg_eq hP_eq

end Problems.residue_thm

