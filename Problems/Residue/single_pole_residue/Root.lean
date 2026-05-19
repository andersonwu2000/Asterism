import Mathlib
import Problems.Residue.single_pole_residue.Defs

open Classical

namespace Problems.Residue.single_pole_residue

theorem main : ∀ {f : ℂ → ℂ} {z₀ : ℂ} {r : ℝ},
  0 < r →
  (∃ R : ℝ, r < R ∧ AnalyticOn ℂ f (Metric.ball z₀ R \ {z₀})) →
  (∮ z in C(z₀, r), f z) = 2 * Real.pi * Complex.I * Complex.residue f z₀ := by sorry

end Problems.Residue.single_pole_residue
