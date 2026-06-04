import Mathlib
import Problems.Minif2f.mathd_algebra_393.Defs

namespace Problems.Minif2f.mathd_algebra_393

-- Direct proof: σ is an Equiv, so σ.2 = σ.invFun is a left inverse of σ.1.
-- From h₀ 2 we get σ.1 2 = 4*8+1 = 33, then σ.left_inv 2 gives σ.2 (σ.1 2) = 2.
-- Rewriting σ.1 2 to 33 yields σ.2 33 = 2.
theorem s665 : ∀ (σ : Equiv ℝ ℝ) (h₀ : ∀ x, σ.1 x = 4 * x ^ 3 + 1), σ.2 33 = 2  := by
  intro σ h₀
  have h1 : σ.1 2 = 33 := by rw [h₀]; norm_num
  have h2 : σ.2 (σ.1 2) = 2 := σ.left_inv 2
  rw [h1] at h2
  exact h2

end Problems.Minif2f.mathd_algebra_393
