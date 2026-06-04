import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs

namespace Problems.Minif2f.imo_1984_p2

-- entry_kind: Backward
theorem seven_cube_from_factorization : ∀ (a b : ℤ), ¬7 ∣ a → ¬7 ∣ b → ¬7 ∣ a + b →
    7 ^ 7 ∣ 7 * a * b * (a + b) * (a ^ 2 + a * b + b ^ 2) ^ 2 →
    (7:ℤ) ^ 3 ∣ a ^ 2 + a * b + b ^ 2 := by sorry

end Problems.Minif2f.imo_1984_p2
