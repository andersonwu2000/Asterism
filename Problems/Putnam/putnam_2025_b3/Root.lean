import Mathlib
import Problems.Putnam.putnam_2025_b3.Defs

set_option linter.style.longLine false

open Finset

namespace Problems.Putnam.putnam_2025_b3

theorem main : putnam_2025_b3_solution ↔
    ∀ S : Set ℕ,
      S.Nonempty →
      (∀ n ∈ S, 0 < n) →
      (∀ n ∈ S, ∀ d : ℕ, 0 < d → d ∣ (2025 ^ n - 15 ^ n) → d ∈ S) →
      S = {n : ℕ | 0 < n} := by sorry

end Problems.Putnam.putnam_2025_b3
