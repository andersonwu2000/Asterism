import Mathlib
import Problems.Minif2f.imo_1984_p2.Defs
import Problems.Minif2f.imo_1984_p2.proofs.L_seven_cube_cancel
import Problems.Minif2f.imo_1984_p2.proofs.L_seven_cube_identity

namespace Problems.Minif2f.imo_1984_p2

-- Reduce (a+b)^7 - a^7 - b^7 = 7·a·b·(a+b)·(a^2+ab+b^2)^2 via algebraic identity,
-- then cancel the prime-7 factors carried by a, b, a+b to get 7^3 ∣ a^2+ab+b^2.
theorem s9425 :
    ∀ (a b : ℤ), ¬7 ∣ a → ¬7 ∣ b → ¬7 ∣ a + b →
      7 ^ 7 ∣ (a + b) ^ 7 - a ^ 7 - b ^ 7 →
      (7:ℤ) ^ 3 ∣ a ^ 2 + a * b + b ^ 2  := by
  intro a b h1 h2 h3 h4
  have h_id := seven_cube_identity
  have h_cancel := seven_cube_cancel
  apply h_cancel a b h1 h2 h3
  rw [← h_id a b]
  exact h4

end Problems.Minif2f.imo_1984_p2
