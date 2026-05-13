import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- entry_kind: Backward
theorem lower_arc_bound : ∀ (x : ℝ), 0 ≤ x → x ≤ 2 * π → Real.cos x ≤ Real.sqrt 2 / 2 → π / 4 ≤ x := by sorry

end Problems.Minif2f.imo_1965_p1
