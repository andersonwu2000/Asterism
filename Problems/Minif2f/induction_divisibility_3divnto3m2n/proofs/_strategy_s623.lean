import Mathlib
import Problems.Minif2f.induction_divisibility_3divnto3m2n.Defs

namespace Problems.Minif2f.induction_divisibility_3divnto3m2n

-- Direct induction on n; succ case factors (k+1)^3 + 2(k+1) = (k^3+2k) + 3(k^2+k+1).
-- Both summands divisible by 3 (ih + explicit factor).
theorem s623 : ∀ (n : ℕ), 3 ∣ n ^ 3 + 2 * n  := by
  intro n
  induction n with
  | zero => decide
  | succ k ih =>
    have : (k + 1) ^ 3 + 2 * (k + 1) = (k ^ 3 + 2 * k) + 3 * (k ^ 2 + k + 1) := by ring
    rw [this]
    exact Nat.dvd_add ih ⟨k ^ 2 + k + 1, rfl⟩

end Problems.Minif2f.induction_divisibility_3divnto3m2n
