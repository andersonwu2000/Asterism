import Mathlib
import Problems.Minif2f.imo_1965_p1.Defs
import Problems.Minif2f.imo_1965_p1.proofs.L_cos_lower_on_upper_arc

open BigOperators Real Nat Topology Rat

namespace Problems.Minif2f.imo_1965_p1

-- By contradiction: if x > 7π/4, then x ∈ (7π/4, 2π] so cos x > √2/2 (sub-goal),
-- but h₂ ∘ h₃ gives 2·cos x ≤ √2, contradicting √2 < 2·cos x. Combinator: linarith.
theorem s9322 : ∀ (x : ℝ) (h₀ : 0 ≤ x) (h₁ : x ≤ 2 * π) (h₂ : 2 * Real.cos x ≤ abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x)))) (h₃ : abs (Real.sqrt (1 + Real.sin (2 * x)) - Real.sqrt (1 - Real.sin (2 * x))) ≤ Real.sqrt 2), x ≤ 7 * π / 4  := by
  intro x h₀ h₁ h₂ h₃
  by_contra hx
  have hx : 7 * π / 4 < x := not_le.mp hx
  have h2cos : 2 * Real.cos x ≤ Real.sqrt 2 := le_trans h₂ h₃
  have hcos_gt : Real.sqrt 2 / 2 < Real.cos x :=
    cos_lower_on_upper_arc x h₀ h₁ h₂ h₃ hx
  linarith

end Problems.Minif2f.imo_1965_p1
