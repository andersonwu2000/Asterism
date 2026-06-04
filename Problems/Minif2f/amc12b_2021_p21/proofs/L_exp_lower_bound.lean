import Mathlib
namespace Problems.Minif2f.amc12b_2021_p21

-- exp_lower_bound: linear lower bound via Real.add_one_le_exp + log-monotonicity to get log 2 ≥ 1/4
-- Substitutes u = t - 3, rewrites 2^t = 8 * 2^u, then 2^u ≥ 1 + u*log2 ≥ 1 + u/4
-- closes 8*(2^u - 1) ≥ 2u i.e. 2*t + 2 ≤ 2^t for t > 3
theorem exp_lower_bound :
    ∀ t : ℝ, 3 < t → 4*t + 2 ≤ (2:ℝ)^t + 2*t := by
  intro t ht
  suffices h : 2 * t + 2 ≤ (2:ℝ)^t by linarith
  set u := t - 3 with hu_def
  have hu_pos : 0 < u := by linarith
  have h2t : (2:ℝ)^t = 8 * (2:ℝ)^u := by
    have heq : t = u + 3 := by simp [hu_def]
    rw [heq, Real.rpow_add (by norm_num : (0:ℝ) < 2)]
    norm_num [Real.rpow_natCast]
    ring
  have h2u_bound : 1 + Real.log 2 * u ≤ (2:ℝ)^u := by
    have h2u_eq : (2:ℝ)^u = Real.exp (Real.log 2 * u) :=
      Real.rpow_def_of_pos (by norm_num) u
    rw [h2u_eq]
    linarith [Real.add_one_le_exp (Real.log 2 * u)]
  have hlog2_lb : (1:ℝ)/4 ≤ Real.log 2 := by
    have hle : Real.exp (1/4) ≤ 2 := by
      have hpos : 0 < Real.exp (1/4) := Real.exp_pos _
      have hexp4 : Real.exp (1/4) ^ 4 = Real.exp 1 := by
        rw [← Real.exp_nat_mul]; norm_num
      have hexp1 : Real.exp 1 ≤ 16 := by linarith [Real.exp_one_lt_d9]
      nlinarith [sq_nonneg (Real.exp (1/4) - 2), sq_nonneg (Real.exp (1/4) + 2)]
    have := Real.log_le_log (Real.exp_pos (1/4 : ℝ)) hle
    rw [Real.log_exp] at this
    exact this
  have hlog2_pos : (0:ℝ) < Real.log 2 := Real.log_pos (by norm_num)
  have h4u : u ≤ 4 * ((2:ℝ)^u - 1) := by nlinarith
  rw [h2t, hu_def]
  nlinarith

end Problems.Minif2f.amc12b_2021_p21
