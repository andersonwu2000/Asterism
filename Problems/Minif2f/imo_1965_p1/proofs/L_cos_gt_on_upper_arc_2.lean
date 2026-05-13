import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- entry_kind: Builder
theorem cos_gt_on_upper_arc_2 :
    ∀ (y : ℝ), 7 * Real.pi / 4 < y → y ≤ 2 * Real.pi → Real.sqrt 2 / 2 < Real.cos y := by sorry

end Problems.Minif2f.imo_1965_p1
