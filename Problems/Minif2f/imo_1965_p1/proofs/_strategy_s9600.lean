import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_lower_arc_bound
import Problems.Minif2f.imo_1965_p1.proofs.L_upper_arc_bound

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- Reduce to `cos x ≤ √2/2` (chain h₂ ∘ h₃ then divide by 2),
-- then split the conjunction into the two arc bounds.
-- Both arc-bound sub-goals depend only on `0 ≤ x ≤ 2π` and `cos x ≤ √2/2`,
-- discarding the unused sqrt/sin combinator from the hypotheses.
theorem s9600 : ∀ (x : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ 2 * π) (h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x)))) (h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2), π / 4 ≤ x ∧ x ≤ 7 * π / 4  := by
  intro x h₀ h₁ h₂ h₃
  have hcos : Real.cos x ≤ Real.sqrt 2 / 2 := by
    have h4 : 2 * Real.cos x ≤ Real.sqrt 2 := le_trans h₂ h₃
    linarith
  have hlow : π / 4 ≤ x := lower_arc_bound x h₀ h₁ hcos
  have hup : x ≤ 7 * π / 4 := upper_arc_bound x h₀ h₁ hcos
  exact ⟨hlow, hup⟩

end Problems.Minif2f.imo_1965_p1
