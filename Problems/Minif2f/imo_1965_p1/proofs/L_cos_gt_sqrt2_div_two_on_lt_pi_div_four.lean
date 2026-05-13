import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- entry_kind: Builder
theorem cos_gt_sqrt2_div_two_on_lt_pi_div_four :
    ∀ (y : ℝ), 0 ≤ y → y < π / 4 → Real.sqrt 2 / 2 < Real.cos y := by sorry

end Problems.Minif2f.imo_1965_p1
