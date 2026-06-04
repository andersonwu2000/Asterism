import Mathlib
import Problems.Minif2f.mathd_algebra_13.Defs

namespace Problems.Minif2f.mathd_algebra_13

-- eqn_x4: plug x=4 into h₀ to reduce to a - b = -16 via norm_num + linarith
theorem eqn_x4 :
    ∀ (a b : ℝ) (h₀ : ∀ x, x - 3 ≠ 0 ∧ x - 5 ≠ 0 →
    4 * x / (x ^ 2 - 8 * x + 15) = a / (x - 3) + b / (x - 5)),
    a - b = -16 := by
  intro a b h₀
  have h4 := h₀ 4 ⟨by norm_num, by norm_num⟩
  simp only [show (4 : ℝ) ^ 2 - 8 * 4 + 15 = -1 by norm_num,
             show (4 : ℝ) - 3 = 1 by norm_num,
             show (4 : ℝ) - 5 = -1 by norm_num,
             show (4 : ℝ) * 4 = 16 by norm_num] at h4
  norm_num at h4
  linarith

end Problems.Minif2f.mathd_algebra_13
