import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_circle_integral_eq_two_radii
import Problems.residue_thm.proofs.L_kernel_analytic_on_inner_ball


namespace Problems.residue_thm

-- Reduce radius independence of `∮ f w / (w - z)` to `circle_integral_eq_two_radii`
-- on the integrand `g w = f w / (w - z)`, using `ρ := min R (dist z z₀)` as a
-- common analyticity radius. The single sub-goal supplies
-- `AnalyticOn ℂ g (ball z₀ ρ \ {z₀})`; `ε₁, ε₂ < ρ` is pure `lt_min`.
theorem s10421
    {f : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} (hR : 0 < R)
    (hf : AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀}))
    {z : ℂ} (hz : z ≠ z₀)
    {ε₁ ε₂ : ℝ} (hε₁ : 0 < ε₁) (hε₂ : 0 < ε₂)
    (hε₁d : ε₁ < dist z z₀) (hε₂d : ε₂ < dist z z₀)
    (hε₁R : ε₁ < R) (hε₂R : ε₂ < R) :
    (∮ w in C(z₀, ε₁), f w / (w - z)) = (∮ w in C(z₀, ε₂), f w / (w - z))  := by
  set ρ : ℝ := min R (dist z z₀) with hρ_def
  have hzdist : (0 : ℝ) < dist z z₀ := dist_pos.mpr hz
  have hρ_pos : 0 < ρ := lt_min hR hzdist
  have hε₁ρ : ε₁ < ρ := lt_min hε₁R hε₁d
  have hε₂ρ : ε₂ < ρ := lt_min hε₂R hε₂d
  have hgan : AnalyticOn ℂ (fun w => f w / (w - z))
      (Metric.ball z₀ ρ \ {z₀}) := kernel_analytic_on_inner_ball hf hz
  exact circle_integral_eq_two_radii hgan hgan hε₁ hε₁ρ hε₂ hε₂ρ

end Problems.residue_thm
