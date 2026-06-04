import Mathlib
import Problems.Minif2f.mathd_algebra_451.Defs

namespace Problems.Minif2f.mathd_algebra_451

-- Direct leaf proof: chain σ.right_inv twice. From h₂ : σ.2 3 = 9 we get
-- σ.1 9 = σ.1 (σ.2 3) = 3, and from h₁ : σ.2 0 = 3 we get σ.1 3 = 0.
theorem s9304 : ∀ (σ : Equiv ℝ ℝ) (h₀ : σ.2 (-15) = 0) (h₁ : σ.2 0 = 3) (h₂ : σ.2 3 = 9) (h₃ : σ.2 9 = 20), σ.1 (σ.1 9) = 0  := by
  intro σ _h₀ h₁ h₂ _h₃
  have e1 : σ.1 9 = 3 := by rw [← h₂]; exact σ.right_inv 3
  have e2 : σ.1 3 = 0 := by rw [← h₁]; exact σ.right_inv 0
  rw [e1, e2]

end Problems.Minif2f.mathd_algebra_451
