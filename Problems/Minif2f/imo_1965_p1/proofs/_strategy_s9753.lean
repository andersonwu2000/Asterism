import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_cos_gt_on_upper_arc_3

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- Contrapose: if y > 7π/4 then cos y > √2/2, contradicting h2.
-- Sub-goal `cos_gt_on_upper_arc_3` strictly weaker (drops the upper conjunct
-- and assumes the strict lower bound y > 7π/4 rather than deriving y ≤ 7π/4).
theorem s9753 : ∀ (y : ℝ), 0 ≤ y → y ≤ 2 * Real.pi → Real.cos y ≤ Real.sqrt 2 / 2 →
    y ≤ 7 * Real.pi / 4 := by
  intro y h0 h1 h2
  by_contra hlt
  have hlt' : 7 * Real.pi / 4 < y := lt_of_not_ge hlt
  have hcos : Real.sqrt 2 / 2 < Real.cos y := cos_gt_on_upper_arc_3 y hlt' h1
  linarith

end Problems.Minif2f.imo_1965_p1
