import Mathlib

namespace Problems.Residue.contour_deformation_annulus

theorem main : ∀ {f : ℂ → ℂ} {c : ℂ} {r₁ r₂ R : ℝ},
  0 < r₁ → r₁ < r₂ → r₂ < R →
  AnalyticOn ℂ f (Metric.ball c R \ {c}) →
  (∮ z in C(c, r₁), f z) = (∮ z in C(c, r₂), f z) := by sorry

end Problems.Residue.contour_deformation_annulus
