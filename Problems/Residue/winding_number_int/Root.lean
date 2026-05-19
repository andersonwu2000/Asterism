import Mathlib
import Problems.Residue.winding_number_int.Defs

namespace Problems.Residue.winding_number_int

theorem main : ∀ {γ : ℝ → ℂ} {a : ℂ},
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  γ 0 = γ 1 →
  a ∉ γ '' Set.Icc 0 1 →
  ∃ k : ℤ,
    (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) =
      2 * Real.pi * Complex.I * k := by sorry

end Problems.Residue.winding_number_int
