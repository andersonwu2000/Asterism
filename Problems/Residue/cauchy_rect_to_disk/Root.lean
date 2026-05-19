import Mathlib

namespace Problems.Residue.cauchy_rect_to_disk

theorem main : ∀ {f : ℂ → ℂ} {c : ℂ} {R : ℝ},
  0 < R →
  DifferentiableOn ℂ f (Metric.closedBall c R) →
  (∮ z in C(c, R), f z) = 0 := by sorry

end Problems.Residue.cauchy_rect_to_disk
