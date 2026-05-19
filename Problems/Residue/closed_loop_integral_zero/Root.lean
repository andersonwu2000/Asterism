import Mathlib

namespace Problems.Residue.closed_loop_integral_zero

theorem main : ∀ {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U →
  (∀ z ∈ U, HasDerivAt F (f z) z) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) U →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 0 := by sorry

end Problems.Residue.closed_loop_integral_zero
