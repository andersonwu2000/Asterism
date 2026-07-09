import Mathlib
import Problems.Putnam.putnam_2004_b2.Defs

set_option linter.style.longLine false

open Nat Topology Filter

namespace Problems.Putnam.putnam_2004_b2

theorem main : ∀ (m n : ℕ)
(mnpos : m > 0 ∧ n > 0),
((m + n)! / ((m + n) ^ (m + n) : ℚ)) < (((m)! / (m ^ m : ℚ)) * ((n)! / (n ^ n : ℚ))) := by sorry

end Problems.Putnam.putnam_2004_b2
