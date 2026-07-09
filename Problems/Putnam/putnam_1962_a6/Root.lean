import Mathlib
import Problems.Putnam.putnam_1962_a6.Defs

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_1962_a6

theorem main : ∀ (S : Set ℚ)
(hSadd : ∀ a ∈ S, ∀ b ∈ S, a + b ∈ S)
(hSprod : ∀ a ∈ S, ∀ b ∈ S, a * b ∈ S)
(hScond : ∀ r : ℚ, (r ∈ S ∨ -r ∈ S ∨ r = 0) ∧ ¬(r ∈ S ∧ -r ∈ S) ∧ ¬(r ∈ S ∧ r = 0) ∧ ¬(-r ∈ S ∧ r = 0)),
S = { r : ℚ | r > 0 } := by sorry

end Problems.Putnam.putnam_1962_a6
