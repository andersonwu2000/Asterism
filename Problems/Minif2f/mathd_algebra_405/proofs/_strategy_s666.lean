import Mathlib
import Problems.Minif2f.mathd_algebra_405.Defs

namespace Problems.Minif2f.mathd_algebra_405

-- Direct: prove S = {1, 2} by extensionality (x²+4x+4 = (x+2)² < 20 forces x ≤ 2),
-- then S.card = 2 is `rfl` on the literal Finset.
theorem s666 : ∀ (S : Finset ℕ) (h₀ : ∀ x, x ∈ S ↔ 0 < x ∧ x ^ 2 + 4 * x + 4 < 20), S.card = 2  := by
  intro S h₀
  have hS : S = ({1, 2} : Finset ℕ) := by
    ext x
    rw [h₀]
    constructor
    · rintro ⟨hpos, hsq⟩
      have hx3 : x < 3 := by nlinarith
      interval_cases x <;> simp
    · intro h
      fin_cases h <;> simp
  rw [hS]
  rfl

end Problems.Minif2f.mathd_algebra_405
