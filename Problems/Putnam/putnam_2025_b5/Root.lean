import Mathlib
import Problems.Putnam.putnam_2025_b5.Defs

set_option linter.style.longLine false

open Finset BigOperators

namespace Problems.Putnam.putnam_2025_b5

theorem main : ∀ (p : ℕ)
    (hp_prime : p.Prime)
    (hp_gt : 3 < p),
(p : ℚ) / 4 - 1 < descentCount p := by sorry

end Problems.Putnam.putnam_2025_b5
