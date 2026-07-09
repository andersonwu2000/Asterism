import Mathlib
import Problems.Putnam.putnam_2025_a5.Defs

set_option linter.style.longLine false

open Finset

namespace Problems.Putnam.putnam_2025_a5

theorem main : ∀ (n : ℕ)
    (hn : 1 ≤ n)
    (s : Fin n → ℤˣ),
(∀ t : Fin n → ℤˣ, f n t ≤ f n s) ↔ s ∈ putnam_2025_a5_solution n := by sorry

end Problems.Putnam.putnam_2025_a5
