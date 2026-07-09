import Mathlib
import Problems.Putnam.putnam_1983_b6.Defs

set_option linter.style.longLine false

open Nat Filter Topology Real Polynomial

namespace Problems.Putnam.putnam_1983_b6

theorem main : ∀ (n : ℕ)
(npos : n > 0)
(α : ℂ)
(hα : α ^ (2 ^ n + 1) - 1 = 0 ∧ α ≠ 1),
(∃ p q : Polynomial ℤ, (aeval α p) ^ 2 + (aeval α q) ^ 2 = -1) := by sorry

end Problems.Putnam.putnam_1983_b6
