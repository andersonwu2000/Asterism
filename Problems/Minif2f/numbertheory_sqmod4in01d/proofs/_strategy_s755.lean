import Mathlib
import Problems.Minif2f.numbertheory_sqmod4in01d.Defs

namespace Problems.Minif2f.numbertheory_sqmod4in01d

-- Direct: case-split on a % 4 ∈ {0,1,2,3}, reduce a^2 % 4 via Int.mul_emod, decide.
theorem s755 : ∀ (a : ℤ), a ^ 2 % 4 = 0 ∨ a ^ 2 % 4 = 1  := by
  intro a
  have hmod : a % 4 = 0 ∨ a % 4 = 1 ∨ a % 4 = 2 ∨ a % 4 = 3 := by omega
  have hsq : a ^ 2 % 4 = ((a % 4) * (a % 4)) % 4 := by
    rw [sq, Int.mul_emod]
  rcases hmod with h | h | h | h <;> rw [hsq, h] <;> decide

end Problems.Minif2f.numbertheory_sqmod4in01d
