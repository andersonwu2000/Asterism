import Mathlib
import Problems.Minif2f.imo_2006_p3.Defs

namespace Problems.Minif2f.imo_2006_p3

-- entry_kind: Builder
theorem factor_cyclic_sum_quartic : ∀ (a b c : ℝ),
    a * b * (a ^ 2 - b ^ 2) + b * c * (b ^ 2 - c ^ 2) + c * a * (c ^ 2 - a ^ 2)
      = (a - b) * (b - c) * (a - c) * (a + b + c) := by grind

end Problems.Minif2f.imo_2006_p3
