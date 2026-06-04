import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs

namespace Problems.Minif2f.imo_1977_p5

-- sq_bound_1009: bound |z| ≤ 31 from z^2 ≤ 1009 via nlinarith product witnesses
theorem sq_bound_1009 : ∀ (z : ℤ), z ^ 2 ≤ 1009 → -31 ≤ z ∧ z ≤ 31 := by
  intro z hz
  constructor <;> nlinarith [sq_nonneg (z + 32), sq_nonneg (z - 32), sq_nonneg z]

end Problems.Minif2f.imo_1977_p5
