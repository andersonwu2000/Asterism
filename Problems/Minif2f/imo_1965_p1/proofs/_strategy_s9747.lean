import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_cos_gt_sqrt2_half_below_pi_div_four

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- Contrapositive: if y < π/4 with 0 ≤ y, then √2/2 < cos y (since cos is
-- strictly decreasing on [0, π] and cos(π/4) = √2/2). The y ≤ 2π hypothesis
-- is unused; only 0 ≤ y places y on the descending arc [0, π/4) ⊂ [0, π].
theorem s9747 : ∀ (y : ℝ), 0 ≤ y → y ≤ 2 * Real.pi →
    Real.cos y ≤ Real.sqrt 2 / 2 → Real.pi / 4 ≤ y := by
  intro y h0 _h2pi hcos
  by_contra hlt
  have hlt' : y < Real.pi / 4 := not_le.mp hlt
  have hgt : Real.sqrt 2 / 2 < Real.cos y :=
    cos_gt_sqrt2_half_below_pi_div_four y h0 hlt'
  linarith

end Problems.Minif2f.imo_1965_p1
