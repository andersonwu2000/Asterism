import Mathlib
import Problems.Minif2f.amc12a_2002_p1.Defs

namespace Problems.Minif2f.amc12a_2002_p1

-- entry_kind: Builder
theorem roots_iff_neg_three_halves_or_five : ∀ (f : ℂ → ℂ), (∀ x, f x = (2 * x + 3) * (x - 4) + (2 * x + 3) * (x - 6)) → ∀ x : ℂ, f x = 0 ↔ x = -3/2 ∨ x = 5 := by grind

end Problems.Minif2f.amc12a_2002_p1
