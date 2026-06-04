import Mathlib
import Problems.Minif2f.mathd_algebra_422.Defs

namespace Problems.Minif2f.mathd_algebra_422

-- Direct proof: σ.1 (σ.2 x) = x with h₀ gives σ.2 x = (x+12)/5; combined with
-- h₁ : σ.1 (x+1) = σ.2 x and h₀ (x+1) = 5(x+1)-12, linarith yields x = 47/24.
theorem s669 : ∀ (x : ℝ) (σ : Equiv ℝ ℝ) (h₀ : ∀ x, σ.1 x = 5 * x - 12) (h₁ : σ.1 (x + 1) = σ.2 x), x = 47 / 24  := by
  intro x σ h₀ h₁
  have hinv : σ.1 (σ.2 x) = x := σ.right_inv x
  have h3 : 5 * (σ.2 x) - 12 = x := by rw [← h₀ (σ.2 x)]; exact hinv
  have h4 : σ.2 x = 5 * (x + 1) - 12 := by rw [← h₁]; exact h₀ (x + 1)
  rw [h4] at h3
  linarith

end Problems.Minif2f.mathd_algebra_422
