import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- entry_kind: Builder
theorem cos_gt_on_upper_arc : ∀ (x : ℝ), 7 * π / 4 < x → x ≤ 2 * π → Real.sqrt 2 / 2 < Real.cos x := by hint

end Problems.Minif2f.imo_1965_p1
