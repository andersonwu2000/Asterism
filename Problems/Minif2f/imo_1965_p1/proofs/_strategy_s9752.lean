import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_cos_gt_sqrt2_half_below_pi_div_four

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- Contrapositive: if y < π/4 (with 0 ≤ y), then cos y > √2/2, contradicting cos y ≤ √2/2.
-- Single sub-goal `cos_gt_sqrt2_half_below_pi_div_four` captures the strict cos lower bound
-- on [0, π/4); upper bound y ≤ 2π is unused on this branch.
theorem s9752 : ∀ (y : ℝ), 0 ≤ y → y ≤ 2 * Real.pi → Real.cos y ≤ Real.sqrt 2 / 2 → Real.pi / 4 ≤ y := by
  intro y h0 hle hcos
  by_contra hne
  have hlt : y < Real.pi / 4 := not_le.mp hne
  have h_cos_gt : Real.sqrt 2 / 2 < Real.cos y :=
    cos_gt_sqrt2_half_below_pi_div_four y h0 hlt
  linarith
end Problems.Minif2f.imo_1965_p1
