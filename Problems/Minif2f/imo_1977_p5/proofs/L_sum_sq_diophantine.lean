import Mathlib
import Problems.Minif2f.imo_1977_p5.Defs

namespace Problems.Minif2f.imo_1977_p5

-- entry_kind: Builder
theorem sum_sq_diophantine : ∀ (a b : ℕ), 41 < a + b → a ^ 2 + b ^ 2 = (a + b) * 44 + 41 → ((a : ℤ) - 22) ^ 2 + ((b : ℤ) - 22) ^ 2 = 1009 := by grind

end Problems.Minif2f.imo_1977_p5
