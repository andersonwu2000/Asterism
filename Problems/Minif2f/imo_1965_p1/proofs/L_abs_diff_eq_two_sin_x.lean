import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- entry_kind: Builder
theorem abs_diff_eq_two_sin_x : ∀ (x : ℝ) (_h₀ : 0 ≤ x) (_h₁ : x ≤ 2 * π)
    (_h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))))
    (_h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2)
    (_hlt : x < π / 4),
    abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) = 2 * Real.sin x := by
  sorry

end Problems.Minif2f.imo_1965_p1
