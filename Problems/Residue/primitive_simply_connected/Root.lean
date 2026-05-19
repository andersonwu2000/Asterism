import Mathlib

namespace Problems.Residue.primitive_simply_connected

theorem main : ∀ {U : Set ℂ} {f : ℂ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  DifferentiableOn ℂ f U →
  ∃ F : ℂ → ℂ, ∀ z ∈ U, HasDerivAt F (f z) z := by sorry

end Problems.Residue.primitive_simply_connected
