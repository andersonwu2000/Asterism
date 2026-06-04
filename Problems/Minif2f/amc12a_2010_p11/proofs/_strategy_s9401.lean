import Mathlib
import Problems.Minif2f.amc12a_2010_p11.Defs

namespace Problems.Minif2f.amc12a_2010_p11

-- Direct proof (leaf-bypass): from `(8/7)^x = 7^7` and `x = logb b (7^7)`,
-- show `b ≠ 1` and `x ≠ 0`, derive `b^x = 7^7` via `Real.rpow_logb`, then
-- equate `(8/7)^x = b^x`, take `Real.log`, cancel `x`, and close via
-- `Real.log_injOn_pos`.
theorem s9401 :
    ∀ (x b : ℝ), 0 < b → (8 / 7 : ℝ) ^ x = 7 ^ 7 → x = Real.logb b (7 ^ 7) → b = 8 / 7  := by
  intro x b h₀ h₁ h₂
  have h87pos : (0 : ℝ) < 8 / 7 := by norm_num
  have h7pow_pos : (0 : ℝ) < 7 ^ 7 := by positivity
  have h7pow_ne_one : (7 : ℝ) ^ 7 ≠ 1 := by
    have : (1 : ℝ) < 7 ^ 7 := by norm_num
    linarith
  have hx_ne : x ≠ 0 := by
    intro hx
    rw [hx, Real.rpow_zero] at h₁
    exact h7pow_ne_one h₁.symm
  have hb_ne_1 : b ≠ 1 := by
    intro hb
    rw [hb] at h₂
    simp only [Real.logb, Real.log_one, div_zero] at h₂
    exact hx_ne h₂
  have hbx : b ^ x = 7 ^ 7 := by
    rw [h₂]
    exact Real.rpow_logb h₀ hb_ne_1 h7pow_pos
  have hpow_eq : (8 / 7 : ℝ) ^ x = b ^ x := h₁.trans hbx.symm
  have hlog_eq : Real.log ((8 / 7 : ℝ) ^ x) = Real.log (b ^ x) := by rw [hpow_eq]
  rw [Real.log_rpow h87pos, Real.log_rpow h₀] at hlog_eq
  have hlog_b_eq : Real.log b = Real.log (8 / 7) := by
    have := mul_left_cancel₀ hx_ne (by linarith [hlog_eq] : x * Real.log b = x * Real.log (8 / 7))
    exact this
  exact Real.log_injOn_pos (Set.mem_Ioi.mpr h₀) (Set.mem_Ioi.mpr h87pos) hlog_b_eq

end Problems.Minif2f.amc12a_2010_p11
