import Mathlib
import Problems.Putnam.putnam_2025_a6.Defs

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_2025_a6

theorem main : ∀ (k : ℕ) (hk : 1 ≤ k),
(2 ^ (2 * k + 2) : ℤ) ∣ (b (2 ^ (k + 1)) - 2 * b (2 ^ k)) ∧
    ¬((2 ^ (2 * k + 3) : ℤ) ∣ (b (2 ^ (k + 1)) - 2 * b (2 ^ k))) := by sorry

end Problems.Putnam.putnam_2025_a6
