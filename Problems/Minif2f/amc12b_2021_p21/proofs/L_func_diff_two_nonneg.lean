import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- func_diff_two_nonneg: 2^(2^√2) ≥ √2^4 = 4 via rpow monotonicity and sq_sqrt
-- RHS: (2:ℝ)^(2:ℝ) = 4 (rpow_natCast), then sqrt(2)^4 = (sqrt(2)^2)^2 = 4 (sq_sqrt).
-- LHS: sqrt(2) ≥ 1 gives 2^sqrt(2) ≥ 2 (rpow_le_rpow_of_exponent_le), then 2^(2^√2) ≥ 2^2 = 4.
theorem func_diff_two_nonneg :
    (2:ℝ)^((2:ℝ)^Real.sqrt 2) - Real.sqrt 2 ^ ((2:ℝ)^(2:ℝ)) ≥ 0 := by
  have hpow22 : (2:ℝ)^(2:ℝ) = 4 := by
    rw [show (2:ℝ) = ((2:ℕ):ℝ) from by norm_cast, Real.rpow_natCast]
    norm_num
  have hRHS : Real.sqrt 2 ^ ((2:ℝ)^(2:ℝ)) = 4 := by
    rw [hpow22, show (4:ℝ) = ((4:ℕ):ℝ) from by norm_cast, Real.rpow_natCast]
    have : Real.sqrt 2 ^ 4 = (Real.sqrt 2 ^ 2) ^ 2 := by ring
    rw [this, Real.sq_sqrt (by norm_num : (2:ℝ) ≥ 0)]
    norm_num
  have hge2 : (2:ℝ)^Real.sqrt 2 ≥ 2 := by
    have hsqrt_ge1 : Real.sqrt 2 ≥ 1 := by
      rw [show (1:ℝ) = Real.sqrt 1 from Real.sqrt_one.symm]
      exact Real.sqrt_le_sqrt (by norm_num)
    have h1 : (2:ℝ)^(1:ℝ) = 2 := Real.rpow_one 2
    calc (2:ℝ)^Real.sqrt 2 ≥ (2:ℝ)^(1:ℝ) := by
          apply Real.rpow_le_rpow_of_exponent_le (by norm_num)
          exact hsqrt_ge1
      _ = 2 := h1
  have hLHS : (2:ℝ)^((2:ℝ)^Real.sqrt 2) ≥ 4 := by
    calc (2:ℝ)^((2:ℝ)^Real.sqrt 2) ≥ (2:ℝ)^(2:ℝ) := by
          apply Real.rpow_le_rpow_of_exponent_le (by norm_num)
          exact hge2
      _ = 4 := hpow22
  linarith

end Problems.Minif2f.amc12b_2021_p21
