import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_func_strict_anti_on_three

namespace Problems.Minif2f.amc12b_2021_p21

-- Strict anti-monotonicity of F(t) = t^(2^√2) − √2^(2^t) on (3, ∞) gives injectivity on that
-- set; the two equations rewrite to F x = 0 = F y, so the (3,∞)-injectivity forces x = y.
theorem s9709 : ∀ x y : ℝ, 0 < x → 0 < y → 3 < x → 3 < y →
    x ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ x →
    y ^ (2 : ℝ) ^ Real.sqrt 2 = Real.sqrt 2 ^ (2 : ℝ) ^ y → x = y  := by
  intro x y hx hy hx3 hy3 hxeq hyeq
  have h_anti := func_strict_anti_on_three
  have hFx : x ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ x = 0 := by linarith
  have hFy : y ^ (2 : ℝ) ^ Real.sqrt 2 - Real.sqrt 2 ^ (2 : ℝ) ^ y = 0 := by linarith
  exact h_anti.injOn (Set.mem_Ioi.mpr hx3) (Set.mem_Ioi.mpr hy3) (by
    simp only [hFx, hFy])

end Problems.Minif2f.amc12b_2021_p21
