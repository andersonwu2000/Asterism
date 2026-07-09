import Mathlib
import Problems.Putnam.putnam_1962_a5.Defs

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_1962_a5

theorem main : ∀ n ≥ 2, putnam_1962_a5_solution n = ∑ k ∈ Finset.Icc 1 n, Nat.choose n k * k^2 := by sorry

end Problems.Putnam.putnam_1962_a5
