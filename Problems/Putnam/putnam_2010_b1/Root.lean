import Mathlib
import Problems.Putnam.putnam_2010_b1.Defs

set_option linter.style.longLine false

open Filter Topology Set

namespace Problems.Putnam.putnam_2010_b1

theorem main : (∃ a : ℕ → ℝ, ∀ m : ℕ, m > 0 → ∑' i : ℕ, (a i)^m = m) ↔ putnam_2010_b1_solution := by sorry

end Problems.Putnam.putnam_2010_b1
