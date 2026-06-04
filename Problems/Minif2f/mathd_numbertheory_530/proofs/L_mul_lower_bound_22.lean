import Mathlib
import Problems.Minif2f.mathd_numbertheory_530.Defs

namespace Problems.Minif2f.mathd_numbertheory_530

-- mul_lower_bound_22: nlinarith with b≥2 and (5b+1)*b≤a*b closes 22≤a*b
theorem mul_lower_bound_22 : ∀ (a b : ℕ), 5 * b < a → a < 6 * b → 22 ≤ a * b := by
  intro a b h1 h2
  have hb : 2 ≤ b := by omega
  have ha : 5 * b + 1 ≤ a := by omega
  have key : (5 * b + 1) * b ≤ a * b := Nat.mul_le_mul_right b ha
  nlinarith [sq_nonneg b]

end Problems.Minif2f.mathd_numbertheory_530
