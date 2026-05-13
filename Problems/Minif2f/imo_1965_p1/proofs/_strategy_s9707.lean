import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_lower_arc_bound_2
import Problems.Minif2f.imo_1965_p1.proofs.L_upper_arc_bound_2

open Real

namespace Problems.Minif2f.imo_1965_p1

-- Chain h₂ ≤ h₃ to get 2·cos x ≤ √2, hence cos x ≤ √2/2; then split the
-- conjunction into the two arc bounds, each phrased with explicit `Real.pi`
-- (the new_*.lean stubs lack `open Real`, so bare `π` would auto-bind there).
-- Adding `open Real` here makes the signature's bare `π` resolve to `Real.pi`,
-- which is what the parent `main` expects.
theorem s9707 : ∀ (x : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ 2 * π) (h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x)))) (h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2), π / 4 ≤ x ∧ x ≤ 7 * π / 4 := by
  intro x h₀ h₁ h₂ h₃
  have hchain : 2 * Real.cos x ≤ Real.sqrt 2 := le_trans h₂ h₃
  have hcos : Real.cos x ≤ Real.sqrt 2 / 2 := by linarith
  have h_lower := lower_arc_bound_2 x h₀ h₁ hcos
  have h_upper := upper_arc_bound_2 x h₀ h₁ hcos
  exact ⟨h_lower, h_upper⟩

end Problems.Minif2f.imo_1965_p1
