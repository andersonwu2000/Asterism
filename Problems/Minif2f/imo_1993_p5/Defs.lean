import Mathlib

set_option maxHeartbeats 0

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1993_p5

/-- Wythoff lower row. -/
noncomputable def goldA (n : ℕ) : ℕ :=
  (⌊(n : ℝ) * Real.goldenRatio⌋).toNat

end Problems.Minif2f.imo_1993_p5
