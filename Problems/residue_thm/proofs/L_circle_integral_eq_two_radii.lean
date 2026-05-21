import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs._strategy_s10298

namespace Problems.residue_thm

-- circle_integral_eq_two_radii: bridge two circle integrals via a shared small radius
-- using s10298 twice (each side has its own analytic ball) with ρ = min r₁ r₂ / 2.
theorem circle_integral_eq_two_radii
    {f : ℂ → ℂ} {z₀ : ℂ} {R₁ R₂ : ℝ}
    (hf₁ : AnalyticOn ℂ f (Metric.ball z₀ R₁ \ {z₀}))
    (hf₂ : AnalyticOn ℂ f (Metric.ball z₀ R₂ \ {z₀}))
    {r₁ : ℝ} (hr₁ : 0 < r₁) (hr₁R₁ : r₁ < R₁)
    {r₂ : ℝ} (hr₂ : 0 < r₂) (hr₂R₂ : r₂ < R₂) :
    (∮ z in C(z₀, r₁), f z) = (∮ z in C(z₀, r₂), f z) := by
  -- pick a small intermediate radius
  set ρ := min r₁ r₂ / 2 with hρ_def
  have hρ_pos : 0 < ρ := by positivity
  have hρr₁ : ρ ≤ r₁ := by
    simp [hρ_def]
    linarith [min_le_left r₁ r₂]
  have hρr₂ : ρ ≤ r₂ := by
    simp [hρ_def]
    linarith [min_le_right r₁ r₂]
  -- bridge: ∮ C(z₀, ρ) = ∮ C(z₀, r₁) using hf₁
  have h1 : (∮ z in C(z₀, ρ), f z) = (∮ z in C(z₀, r₁), f z) :=
    s10298 hf₁ hρ_pos hρr₁ hr₁R₁
  -- bridge: ∮ C(z₀, ρ) = ∮ C(z₀, r₂) using hf₂
  have h2 : (∮ z in C(z₀, ρ), f z) = (∮ z in C(z₀, r₂), f z) :=
    s10298 hf₂ hρ_pos hρr₂ hr₂R₂
  exact h1.symm.trans h2

end Problems.residue_thm

