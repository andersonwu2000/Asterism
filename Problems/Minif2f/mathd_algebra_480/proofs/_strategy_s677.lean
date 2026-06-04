import Mathlib
import Problems.Minif2f.mathd_algebra_480.Defs

namespace Problems.Minif2f.mathd_algebra_480

-- Direct: π lies in [0, 4) since 0 ≤ π (Real.pi_nonneg) and π < 4 (Real.pi_lt_four),
-- so apply h₁ to conclude f π = 2.
open Real in
theorem s677 : ∀ (f : ℝ → ℝ) (h₀ : ∀ x < 0, f x = -x ^ 2 - 1) (h₁ : ∀ x, 0 ≤ x ∧ x < 4 → f x = 2) (h₂ : ∀ x ≥ 4, f x = Real.sqrt x), f π = 2  := by
  intro f h₀ h₁ h₂
  apply h₁
  refine ⟨Real.pi_nonneg, ?_⟩
  exact Real.pi_lt_four

end Problems.Minif2f.mathd_algebra_480
