import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs

namespace Problems.Minif2f.imo_1984_p2

-- Direct bound: if a+b ≤ 18 then 0 < a² + ab + b² ≤ (a+b)² ≤ 324 < 343 = 7³,
-- contradicting 7³ ∣ a² + ab + b² via Int.le_of_dvd. The ¬7∣ hypotheses are unused.
theorem s9424 :
    ∀ (a b : ℤ), 0 < a → 0 < b → ¬7 ∣ a → ¬7 ∣ b → ¬7 ∣ a + b →
      (7:ℤ) ^ 3 ∣ a ^ 2 + a * b + b ^ 2 →
      19 ≤ a + b  := by
  intro a b ha hb _ _ _ hdvd
  by_contra hlt
  rw [not_le] at hlt
  have h1 : 0 < a ^ 2 + a * b + b ^ 2 := by positivity
  have h2 : a ^ 2 + a * b + b ^ 2 < 7 ^ 3 := by nlinarith [sq_nonneg (a + b)]
  have h3 : (7:ℤ) ^ 3 ≤ a ^ 2 + a * b + b ^ 2 := Int.le_of_dvd h1 hdvd
  linarith

end Problems.Minif2f.imo_1984_p2
