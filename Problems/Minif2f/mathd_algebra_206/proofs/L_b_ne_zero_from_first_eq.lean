import Mathlib
import Problems.Minif2f.mathd_algebra_206.Defs

namespace Problems.Minif2f.mathd_algebra_206

-- entry_kind: Builder
theorem b_ne_zero_from_first_eq : ∀ (a b : ℝ), 2*a ≠ b → (2*a)^2 + a*(2*a) + b = 0 → b ≠ 0 := by grind

end Problems.Minif2f.mathd_algebra_206
