import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs
import Problems.Minif2f.imo_1977_p5.proofs.L_int_sum_sq_1009
import Problems.Minif2f.imo_1977_p5.proofs.L_sum_sq_diophantine

namespace Problems.Minif2f.imo_1977_p5

-- Reduce to integer sum-of-squares Diophantine: (a-22)^2 + (b-22)^2 = 1009
-- sum_sq_diophantine derives the equation from hypotheses; int_sum_sq_1009 dispatches
-- the abstract Diophantine x^2+y^2=1009 over ℤ into |x|,|y| ∈ {15,28} cases.
theorem s9482 : ∀ (a b : ℕ), 41 < a + b → a ^ 2 + b ^ 2 = (a + b) * 44 + 41 → abs ((a : ℤ) - 22) = 15 ∧ abs ((b : ℤ) - 22) = 28 ∨ abs ((a : ℤ) - 22) = 28 ∧ abs ((b : ℤ) - 22) = 15  := by
  intro a b h0 h1
  have h_sum_sq_diophantine := sum_sq_diophantine a b h0 h1
  exact int_sum_sq_1009 ((a : ℤ) - 22) ((b : ℤ) - 22) h_sum_sq_diophantine

end Problems.Minif2f.imo_1977_p5
