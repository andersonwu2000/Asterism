import Mathlib
import Problems.Putnam.putnam_1976_b1.Defs

set_option linter.style.longLine false

open Polynomial Filter Topology

namespace Problems.Putnam.putnam_1976_b1

theorem main : Tendsto (fun n : ℕ => ((1 : ℝ)/n)*∑ k ∈ Finset.Icc (1 : ℤ) n, (Int.floor ((2*n)/k) - 2*Int.floor (n/k))) atTop
(𝓝 (Real.log putnam_1976_b1_solution.1 - putnam_1976_b1_solution.2)) := by sorry

end Problems.Putnam.putnam_1976_b1
