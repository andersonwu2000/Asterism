import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_cos_gt_on_upper_arc

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- By contradiction: if x > 7π/4 then cos x > √2/2 (cos is decreasing in y = 2π - x on [0, π/4)).
-- One sub-goal `cos_gt_on_upper_arc`: pure cos-on-arc bound, closes via linarith vs. h₂.
theorem s9654 : ∀ (x : ℝ), 0 ≤ x → x ≤ 2 * π → Real.cos x ≤ Real.sqrt 2 / 2 → x ≤ 7 * π / 4  := by
  intro x h0 h1 h2
  by_contra hlt
  push_neg at hlt
  have key : Real.sqrt 2 / 2 < Real.cos x := cos_gt_on_upper_arc x hlt h1
  linarith

end Problems.Minif2f.imo_1965_p1
