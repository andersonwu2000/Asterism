import Mathlib
import Problems.Putnam.putnam_2025_a4.Defs

set_option linter.style.longLine false

namespace Problems.Putnam.putnam_2025_a4

theorem main : IsLeast {k : ℕ | ∃ A : Fin 2025 → Matrix (Fin k) (Fin k) ℝ,
    ∀ i j : Fin 2025, i ≤ j →
      (A i * A j = A j * A i ↔ j.val - i.val ∈ ({0, 1, 2024} : Set ℕ))}
  putnam_2025_a4_solution := by sorry

end Problems.Putnam.putnam_2025_a4
