import Mathlib
import Problems.Putnam.putnam_2025_b6.Defs

set_option linter.style.longLine false

open Real

namespace Problems.Putnam.putnam_2025_b6

theorem main : IsGreatest
      {r : ℝ | ∃ g : ℕ → ℕ, (∀ n : ℕ, 0 < n → 0 < g n) ∧
        ∀ n : ℕ, 0 < n → ((g (g n) : ℝ) ^ r) ≤ (g (n + 1) : ℝ) - (g n : ℝ)}
      putnam_2025_b6_solution := by sorry

end Problems.Putnam.putnam_2025_b6
