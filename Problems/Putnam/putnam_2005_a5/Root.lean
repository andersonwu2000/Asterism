import Mathlib
import Problems.Putnam.putnam_2005_a5.Defs

set_option linter.style.longLine false

open Nat Set

namespace Problems.Putnam.putnam_2005_a5

theorem main : ∫ x in (0:ℝ)..1, (Real.log (x+1))/(x^2 + 1) = putnam_2005_a5_solution := by sorry

end Problems.Putnam.putnam_2005_a5
