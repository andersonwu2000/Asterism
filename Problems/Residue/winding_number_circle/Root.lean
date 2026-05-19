import Mathlib
import Problems.Residue.winding_number_circle.Defs

namespace Problems.Residue.winding_number_circle

theorem main : ∀ (c : ℂ) (R : ℝ) (a : ℂ),
  0 < R →
  (‖a - c‖ < R → Complex.windingNumber (fun t => c + R * Complex.exp (2 * Real.pi * Complex.I * t)) a = 1) ∧
  (R < ‖a - c‖ → Complex.windingNumber (fun t => c + R * Complex.exp (2 * Real.pi * Complex.I * t)) a = 0) := by sorry

end Problems.Residue.winding_number_circle
