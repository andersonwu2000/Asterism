import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- Direct chain: 2^t * log 2 * log √2 < 2^√2 * t⁻¹ on (1, √2).
-- Bound LHS via 2^t ≤ 2^√2 (monotonicity), then via numeric
-- `log 2 * log √2 < 1/2` (uses `log_sqrt` + `log_two_lt_d9/gt_d9`), then
-- `1/2 < t⁻¹` since `t < √2 < 2` ⇒ `t⁻¹ > 1/2`. Chain closes the
-- subtraction with `linarith`.
theorem s9829 :
    ∀ t ∈ Set.Ioo (1:ℝ) (Real.sqrt 2),
        (2:ℝ)^t * Real.log 2 * Real.log (Real.sqrt 2)
          - (2:ℝ)^Real.sqrt 2 * t⁻¹ < 0  := by
  intro t ht
  obtain ⟨h1t, ht2⟩ := ht
  have ht_pos : (0:ℝ) < t := by linarith
  have h2_pos : (0:ℝ) < (2:ℝ) := by norm_num
  have hsqrt2_pos : (0:ℝ) < Real.sqrt 2 := Real.sqrt_pos.mpr (by norm_num)
  have hsqrt2_lt_two : Real.sqrt 2 < 2 := by
    have h4 : Real.sqrt 4 = 2 := by
      rw [show (4:ℝ) = 2^2 from by norm_num]; exact Real.sqrt_sq (by norm_num)
    calc Real.sqrt 2 < Real.sqrt 4 := Real.sqrt_lt_sqrt (by norm_num) (by norm_num)
      _ = 2 := h4
  have ht_lt_two : t < 2 := lt_trans ht2 hsqrt2_lt_two
  have hpow_s_pos : (0:ℝ) < (2:ℝ)^Real.sqrt 2 := Real.rpow_pos_of_pos h2_pos _
  have h_log_prod : Real.log 2 * Real.log (Real.sqrt 2) < 1/2 := by
    rw [Real.log_sqrt (by norm_num : (0:ℝ) ≤ 2)]
    have h1 := Real.log_two_lt_d9
    have h2 := Real.log_two_gt_d9
    nlinarith
  have h_pow_mono : (2:ℝ)^t ≤ (2:ℝ)^Real.sqrt 2 :=
    Real.rpow_le_rpow_of_exponent_le (by norm_num) ht2.le
  have h_inv_gt_half : (1:ℝ)/2 < t⁻¹ := by
    rw [lt_inv_comm₀ (by norm_num : (0:ℝ) < 1/2) ht_pos]
    linarith
  have h_log_nonneg : 0 ≤ Real.log 2 * Real.log (Real.sqrt 2) := by
    apply mul_nonneg
    · exact Real.log_nonneg (by norm_num)
    · exact Real.log_nonneg (by
        rw [show (1:ℝ) = Real.sqrt 1 from (Real.sqrt_one).symm]
        exact Real.sqrt_le_sqrt (by norm_num))
  have step1 : (2:ℝ)^t * Real.log 2 * Real.log (Real.sqrt 2) ≤
               (2:ℝ)^Real.sqrt 2 * (Real.log 2 * Real.log (Real.sqrt 2)) := by
    rw [mul_assoc]
    exact mul_le_mul_of_nonneg_right h_pow_mono h_log_nonneg
  have step2 : (2:ℝ)^Real.sqrt 2 * (Real.log 2 * Real.log (Real.sqrt 2)) <
               (2:ℝ)^Real.sqrt 2 * (1/2) :=
    mul_lt_mul_of_pos_left h_log_prod hpow_s_pos
  have step3 : (2:ℝ)^Real.sqrt 2 * (1/2) < (2:ℝ)^Real.sqrt 2 * t⁻¹ :=
    mul_lt_mul_of_pos_left h_inv_gt_half hpow_s_pos
  linarith

end Problems.Minif2f.amc12b_2021_p21
