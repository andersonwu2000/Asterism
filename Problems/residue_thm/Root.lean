import Mathlib

namespace Problems.residue_thm

theorem main : ∀ {f : ℂ → ℂ} {z₀ : ℂ} {r : ℝ},
    0 < r →
    AnalyticOn ℂ f (Metric.ball z₀ r \ {z₀}) →
    (∮ z in circle z₀ r, f z) = 2 * Real.pi * Complex.I *
      Complex.residue f z₀ := by sorry

end Problems.residue_thm
