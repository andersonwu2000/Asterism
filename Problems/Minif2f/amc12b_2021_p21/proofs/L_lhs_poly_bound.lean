import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs

namespace Problems.Minif2f.amc12b_2021_p21

-- lhs_poly_bound: bound 2^√2 * t^(2^√2-1) ≤ 3*t^2 for t>3 via 2^√2≤3 and exponent monotonicity
-- Chain: 2^√2 ≤ 2^(3/2)=2√2 ≤ 3 (since √2≤3/2), then t^(2^√2-1) ≤ t^2 (exponents ≤2, t≥1)
theorem lhs_poly_bound :
    ∀ t : ℝ, 3 < t →
      (2 : ℝ) ^ Real.sqrt 2 * t ^ ((2 : ℝ) ^ Real.sqrt 2 - 1) ≤ 3 * t ^ 2 := by
  intro t ht
  have ht1 : (1 : ℝ) ≤ t := by linarith
  have hsq2_le : Real.sqrt 2 ≤ 3 / 2 := by
    nlinarith [Real.sq_sqrt (show (0:ℝ) ≤ 2 by norm_num), Real.sqrt_nonneg 2]
  have h2sqrt2_le3 : (2:ℝ) ^ Real.sqrt 2 ≤ 3 := by
    have step1 : (2:ℝ) ^ Real.sqrt 2 ≤ (2:ℝ) ^ (3/2 : ℝ) :=
      Real.rpow_le_rpow_of_exponent_le (by norm_num : 1 ≤ (2:ℝ)) hsq2_le
    have step2 : (2:ℝ) ^ (3/2 : ℝ) = 2 * Real.sqrt 2 := by
      rw [show (3/2 : ℝ) = 1 + 1/2 by ring, Real.rpow_add (by norm_num : (0:ℝ) < 2),
          Real.rpow_one, ← Real.sqrt_eq_rpow]
    have step3 : 2 * Real.sqrt 2 ≤ 3 := by
      nlinarith [Real.sq_sqrt (show (0:ℝ) ≤ 2 by norm_num), Real.sqrt_nonneg 2]
    linarith
  have hexp_le : (2:ℝ) ^ Real.sqrt 2 - 1 ≤ 2 := by linarith
  have htpow_le : t ^ ((2:ℝ) ^ Real.sqrt 2 - 1) ≤ t ^ (2:ℝ) :=
    Real.rpow_le_rpow_of_exponent_le ht1 hexp_le
  have ht2_eq : t ^ (2:ℝ) = t ^ 2 := by
    rw [← Real.rpow_natCast t 2]; norm_num
  calc (2:ℝ) ^ Real.sqrt 2 * t ^ ((2:ℝ) ^ Real.sqrt 2 - 1)
      ≤ 3 * t ^ ((2:ℝ) ^ Real.sqrt 2 - 1) := by
        apply mul_le_mul_of_nonneg_right h2sqrt2_le3
        exact Real.rpow_nonneg (by linarith) _
    _ ≤ 3 * t ^ (2:ℝ) := by
        exact mul_le_mul_of_nonneg_left htpow_le (by norm_num)
    _ = 3 * t ^ 2 := by rw [ht2_eq]

end Problems.Minif2f.amc12b_2021_p21
