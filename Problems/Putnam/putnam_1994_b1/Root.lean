import Mathlib
import Problems.Putnam.putnam_1994_b1.Defs

set_option linter.style.longLine false

open Filter Topology

namespace Problems.Putnam.putnam_1994_b1

theorem main : ∀ (n : ℤ),
n ∈ putnam_1994_b1_solution ↔
    (0 < n ∧ {m : ℕ | |n - m ^ 2| ≤ 250}.encard = 15) := by sorry

end Problems.Putnam.putnam_1994_b1
