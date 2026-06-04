import Mathlib
import Problems.Minif2f.mathd_algebra_493.Defs

namespace Problems.Minif2f.mathd_algebra_493

-- Direct numeric computation: f(4) = 16 - 4·2 + 1 = 9, then f(9) = 81 - 4·3 + 1 = 70.
-- Reduces √4 = 2 and √9 = 3 via `Real.sqrt_sq` on perfect squares; `norm_num` closes arithmetic.
theorem s679 : ∀ (f : ℝ → ℝ) (h₀ : ∀ x, f x = x ^ 2 - 4 * Real.sqrt x + 1), f (f 4) = 70  := by
  intro f h₀
  have h4 : Real.sqrt 4 = 2 := by
    rw [show (4 : ℝ) = 2^2 by norm_num, Real.sqrt_sq (by norm_num : (2:ℝ) ≥ 0)]
  have h9 : Real.sqrt 9 = 3 := by
    rw [show (9 : ℝ) = 3^2 by norm_num, Real.sqrt_sq (by norm_num : (3:ℝ) ≥ 0)]
  have hf4 : f 4 = 9 := by rw [h₀]; rw [h4]; norm_num
  rw [hf4, h₀, h9]; norm_num

end Problems.Minif2f.mathd_algebra_493
