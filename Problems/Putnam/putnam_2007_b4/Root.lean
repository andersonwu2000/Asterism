import Mathlib
import Problems.Putnam.putnam_2007_b4.Defs

set_option linter.style.longLine false

open Set Nat Function

namespace Problems.Putnam.putnam_2007_b4

theorem main : ∀ (n : ℕ) (npos : n > 0),
({(P, Q) : (Polynomial ℝ) × (Polynomial ℝ) | P ^ 2 + Q ^ 2 = Polynomial.X ^ (2 * n) + 1 ∧ P.degree > Q.degree}.ncard = putnam_2007_b4_solution n) := by sorry

end Problems.Putnam.putnam_2007_b4
