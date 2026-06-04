import Mathlib
import Problems.Minif2f.mathd_algebra_59.Defs

namespace Problems.Minif2f.mathd_algebra_59

-- Direct leaf proof: `4^b + 8 = 12 ⇒ 4^b = 4 = 4^1`, then rpow injectivity in
-- the exponent (since base 4 > 1) yields `b = 1`. No sub-goals — single-file ship.
theorem s9262 : ∀ (b : ℝ) (h₀ : (4 : ℝ) ^ b + 2 ^ 3 = 12), b = 1  := by
  intro b h₀
  have h1 : (4 : ℝ) ^ b = 4 := by linarith
  have h2 : (4 : ℝ) ^ b = (4 : ℝ) ^ (1 : ℝ) := by rw [Real.rpow_one]; exact h1
  exact (Real.strictMono_rpow_of_base_gt_one (by norm_num : (1:ℝ) < 4)).injective h2

end Problems.Minif2f.mathd_algebra_59
