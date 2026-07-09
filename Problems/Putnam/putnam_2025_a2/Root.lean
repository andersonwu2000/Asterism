import Mathlib
import Problems.Putnam.putnam_2025_a2.Defs

set_option linter.style.longLine false

open Real

namespace Problems.Putnam.putnam_2025_a2

theorem main : ∀ (a b : ℝ),
((a, b) = putnam_2025_a2_solution) ↔
  (IsGreatest {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x} a ∧
   IsLeast {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)} b) := by sorry

end Problems.Putnam.putnam_2025_a2
