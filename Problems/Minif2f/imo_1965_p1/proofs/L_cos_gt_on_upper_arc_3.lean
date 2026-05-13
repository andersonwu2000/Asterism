import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- cos_gt_on_upper_arc_3: cos z > √2/2 on (7π/4, 2π] via Real.strictAntiOn_cos after
-- substituting cos(2π - z) = cos z and comparing with cos(π/4) = √2/2.
theorem cos_gt_on_upper_arc_3 : ∀ (z : ℝ), 7 * Real.pi / 4 < z → z ≤ 2 * Real.pi →
    Real.sqrt 2 / 2 < Real.cos z := by
  intro z hz1 hz2
  have hpi := Real.pi_pos
  rw [← Real.cos_two_pi_sub]
  have hcos_pi4 : Real.cos (Real.pi / 4) = Real.sqrt 2 / 2 := Real.cos_pi_div_four
  rw [← hcos_pi4]
  apply Real.strictAntiOn_cos
  · constructor
    · linarith
    · linarith [Real.pi_le_four]
  · constructor
    · linarith
    · linarith [Real.pi_le_four]
  · linarith

end Problems.Minif2f.imo_1965_p1
