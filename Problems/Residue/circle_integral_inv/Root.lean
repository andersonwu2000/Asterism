import Mathlib

namespace Problems.Residue.circle_integral_inv

theorem main : ∀ (c : ℂ) (R : ℝ),
  0 < R →
  (∮ z in C(c, R), (z - c)⁻¹) = 2 * Real.pi * Complex.I := by sorry

end Problems.Residue.circle_integral_inv
