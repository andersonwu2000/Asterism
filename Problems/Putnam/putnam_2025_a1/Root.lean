import Mathlib
import Problems.Putnam.putnam_2025_a1.Defs

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_2025_a1

theorem main : ∀ (m n : ℕ → ℕ)
  (hm : ∀ k : ℕ, 0 < m k)
  (hn : ∀ k : ℕ, 0 < n k)
  (h_distinct : m 0 ≠ n 0)
  (h_coprime : ∀ k : ℕ, 0 < k → Nat.Coprime (m k) (n k))
  (h_recurrence : ∀ k : ℕ,
    (m (k + 1) : ℚ) / (n (k + 1) : ℚ) = (2 * (m k : ℚ) + 1) / (2 * (n k : ℚ) + 1)),
{k : ℕ | ¬Nat.Coprime (2 * m k + 1) (2 * n k + 1)}.Finite := by sorry

end Problems.Putnam.putnam_2025_a1
