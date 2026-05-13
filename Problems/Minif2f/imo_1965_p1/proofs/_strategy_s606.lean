import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_lower_bound
import Problems.Minif2f.imo_1965_p1.proofs.L_upper_bound

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- Split conjunction π/4 ≤ x ∧ x ≤ 7π/4 into lower-bound and upper-bound halves.
-- Each half carries the full hypothesis set; combinator is And.intro.
theorem s606 : ∀ (x : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ 2 * π) (h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x)))) (h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2), π / 4 ≤ x ∧ x ≤ 7 * π / 4  := by
  intro x h₀ h₁ h₂ h₃
  have h_lo : π / 4 ≤ x := lower_bound x h₀ h₁ h₂ h₃
  have h_hi : x ≤ 7 * π / 4 := upper_bound x h₀ h₁ h₂ h₃
  exact And.intro h_lo h_hi

end Problems.Minif2f.imo_1965_p1
