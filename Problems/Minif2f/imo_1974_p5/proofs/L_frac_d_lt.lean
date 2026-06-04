import Mathlib
import Problems.Minif2f.imo_1974_p5.Defs

namespace Problems.Minif2f.imo_1974_p5

-- entry_kind: Builder
theorem frac_d_lt : ∀ (a b c d : ℝ), 0 < a → 0 < b → 0 < c → 0 < d →
    d / (a + b + c + d) < d / (a + c + d) := by bound

end Problems.Minif2f.imo_1974_p5
