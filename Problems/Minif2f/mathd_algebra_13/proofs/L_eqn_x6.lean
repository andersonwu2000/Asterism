import Mathlib
import Problems.Minif2f.mathd_algebra_13.Defs

namespace Problems.Minif2f.mathd_algebra_13

-- eqn_x6: plug x=6 into h₀ to get 8 = a/3 + b, then use 3*(a/3) = a to conclude a + 3*b = 24
theorem eqn_x6 : ∀ (a b : ℝ) (h₀ : ∀ x, x - 3 ≠ 0 ∧ x - 5 ≠ 0 → 4 * x / (x ^ 2 - 8 * x + 15) = a / (x - 3) + b / (x - 5)), a + 3 * b = 24 := by
  intro a b h₀
  have h6 := h₀ 6 ⟨by norm_num, by norm_num⟩
  simp only [show (6 : ℝ) ^ 2 - 8 * 6 + 15 = 3 by norm_num,
             show (6 : ℝ) - 3 = 3 by norm_num,
             show (6 : ℝ) - 5 = 1 by norm_num,
             show (4 : ℝ) * 6 = 24 by norm_num] at h6
  norm_num at h6
  have key : 3 * (a / 3) = a := by ring
  linarith

end Problems.Minif2f.mathd_algebra_13
