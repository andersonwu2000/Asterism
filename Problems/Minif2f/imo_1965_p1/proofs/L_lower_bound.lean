import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- entry_kind: Backward
theorem lower_bound : ∀ (x : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ 2 * π) (h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x)))) (h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2), π / 4 ≤ x := by sorry

end Problems.Minif2f.imo_1965_p1
