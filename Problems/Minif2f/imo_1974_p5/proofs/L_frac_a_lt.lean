import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- entry_kind: Builder
theorem frac_a_lt : ∀ (a b c d : ℝ), 0 < a → 0 < b → 0 < c → 0 < d →
    a / (a + b + c + d) < a / (a + b + d) := by bound

end Problems.Minif2f.imo_1974_p5
