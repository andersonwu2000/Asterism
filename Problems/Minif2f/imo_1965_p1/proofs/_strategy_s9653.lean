import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_cos_gt_sqrt2_div_two_on_lt_pi_div_four

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- By contradiction: assume x < π/4. Since cos is strictly antitone on [0, π]
-- and cos(π/4) = √2/2, we have cos x > √2/2, contradicting h₂. Hypothesis
-- `x ≤ 2π` is unused. The sub-goal abstracts the cos-on-arc fact.
theorem s9653 : ∀ (x : ℝ), 0 ≤ x → x ≤ 2 * π → Real.cos x ≤ Real.sqrt 2 / 2 → π / 4 ≤ x  := by
  intro x h0 _ h2
  by_contra h
  push_neg at h
  have hgt := cos_gt_sqrt2_div_two_on_lt_pi_div_four x h0 h
  linarith

end Problems.Minif2f.imo_1965_p1
