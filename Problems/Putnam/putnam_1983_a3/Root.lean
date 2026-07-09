import Mathlib
import Problems.Putnam.putnam_1983_a3.Defs

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_1983_a3

theorem main : ∀ (p : ℕ)
(F : ℕ → ℕ)
(poddprime : Odd p ∧ p.Prime)
(hF : ∀ n : ℕ, F n = ∑ i ∈ Finset.range (p - 1), (i + 1) * n ^ i),
∀ a ∈ Finset.Icc 1 p, ∀ b ∈ Finset.Icc 1 p, a ≠ b → ¬(F a ≡ F b [MOD p]) := by sorry

end Problems.Putnam.putnam_1983_a3
