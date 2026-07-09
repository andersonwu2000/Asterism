import Mathlib
import Problems.Putnam.putnam_2005_b6.Defs

set_option linter.style.longLine false

open Nat Set

namespace Problems.Putnam.putnam_2005_b6

theorem main : ∀ (n : ℕ)
(v : Equiv.Perm (Fin n) → ℕ)
(npos : n ≥ 1)
(hv : ∀ p : Equiv.Perm (Fin n), v p = Set.encard {i : Fin n | p i = i}),
(∑ p : Equiv.Perm (Fin n), (Equiv.Perm.signAux p : ℤ) / (v p + 1 : ℝ)) = (-1) ^ (n + 1) * (n / (n + 1 : ℝ)) := by sorry

end Problems.Putnam.putnam_2005_b6
