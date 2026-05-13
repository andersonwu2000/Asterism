import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- cos_gt_sqrt2_half_below_pi_div_four: strictAntiOn_cos on [0,π] + cos(π/4)=√2/2
-- For z ∈ [0, π/4), cosine is strictly decreasing on [0, π], so cos z > cos(π/4) = √2/2.
theorem cos_gt_sqrt2_half_below_pi_div_four :
    ∀ (z : ℝ), 0 ≤ z → z < Real.pi / 4 → Real.sqrt 2 / 2 < Real.cos z := by
  intro z hz0 hzlt
  have hpi4 : Real.pi / 4 ∈ Set.Icc (0 : ℝ) Real.pi :=
    ⟨by positivity, by linarith [Real.pi_pos]⟩
  have hz_mem : z ∈ Set.Icc (0 : ℝ) Real.pi :=
    ⟨hz0, by linarith [Real.pi_pos]⟩
  have h := Real.strictAntiOn_cos hz_mem hpi4 hzlt
  rw [Real.cos_pi_div_four] at h
  exact h

end Problems.Minif2f.imo_1965_p1
