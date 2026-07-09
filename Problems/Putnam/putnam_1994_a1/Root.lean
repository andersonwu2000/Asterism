import Mathlib
import Problems.Putnam.putnam_1994_a1.Defs

set_option linter.style.longLine false

open Filter Topology

namespace Problems.Putnam.putnam_1994_a1

theorem main : ∀ (a : ℕ → ℝ)
    (ha : ∀ n ≥ 1, 0 < a n ∧ a n ≤ a (2 * n) + a (2 * n + 1)),
Tendsto (fun N : ℕ => ∑ n : Set.Icc 1 N, a n) atTop atTop := by sorry

end Problems.Putnam.putnam_1994_a1
