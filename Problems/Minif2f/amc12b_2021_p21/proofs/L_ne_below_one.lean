import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- ne_below_one: For y ∈ (0,1), LHS = y^(2^√2) < 1 < √2^(2^y) = RHS
theorem ne_below_one : ∀ y : ℝ, 0 < y → y < Real.sqrt 2 → y < 1 →
    y ^ (2 : ℝ) ^ Real.sqrt 2 ≠ Real.sqrt 2 ^ (2 : ℝ) ^ y := by
  intro y hy _ hy1
  have h2pos : (0 : ℝ) < 2 := by norm_num
  have h2y : (0 : ℝ) < (2 : ℝ) ^ y := Real.rpow_pos_of_pos h2pos y
  have h2s : (0 : ℝ) < (2 : ℝ) ^ Real.sqrt 2 := Real.rpow_pos_of_pos h2pos _
  have hLHS : y ^ (2 : ℝ) ^ Real.sqrt 2 < 1 :=
    Real.rpow_lt_one (le_of_lt hy) hy1 h2s
  have hsqrt2_gt1 : (1 : ℝ) < Real.sqrt 2 := by
    have : (1 : ℝ) < 2 := by norm_num
    calc (1 : ℝ) = Real.sqrt 1 := (Real.sqrt_one).symm
      _ < Real.sqrt 2 := Real.sqrt_lt_sqrt (by norm_num) this
  have hRHS : 1 < Real.sqrt 2 ^ (2 : ℝ) ^ y := by
    rw [Real.one_lt_rpow_iff_of_pos (lt_trans one_pos hsqrt2_gt1)]
    left; exact ⟨hsqrt2_gt1, h2y⟩
  linarith

end Problems.Minif2f.amc12b_2021_p21
