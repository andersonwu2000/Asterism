import Mathlib
import Problems.Putnam.putnam_2005_a3.Defs

set_option linter.style.longLine false

open Nat Set

namespace Problems.Putnam.putnam_2005_a3

theorem main : ∀ (p : Polynomial ℂ)
    (n : ℕ)
    (hn : 0 < n)
    (g : ℂ → ℂ)
    (pdeg : p.degree = n)
    (pzeros : ∀ z : ℂ, p.eval z = 0 → ‖z‖ = 1)
    (hg : ∀ z : ℂ, g z = (p.eval z) / z ^ ((n : ℂ) / 2))
    (z : ℂ)
    (hz : z ≠ 0 ∧ DifferentiableAt ℂ g z ∧ deriv g z = 0),
‖z‖ = 1 := by sorry

end Problems.Putnam.putnam_2005_a3
