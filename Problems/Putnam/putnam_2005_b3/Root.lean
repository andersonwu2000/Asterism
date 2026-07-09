import Mathlib
import Problems.Putnam.putnam_2005_b3.Defs

set_option linter.style.longLine false

open Nat Set

namespace Problems.Putnam.putnam_2005_b3

theorem main : ∀ (f : ℝ → ℝ)
    (hf : ∀ x > 0, 0 < f x)
    (hf' : DifferentiableOn ℝ f (Ioi 0)),
(∃ a > 0, ∀ x > 0, deriv f (a / x) = x / f x) ↔ f ∈ putnam_2005_b3_solution := by sorry

end Problems.Putnam.putnam_2005_b3
