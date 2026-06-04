import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_lhs_simp_g_three
import Problems.Minif2f.amc12b_2021_p21.proofs.L_pow_sqrt2_lower
import Problems.Minif2f.amc12b_2021_p21.proofs.L_rational_bound_log

namespace Problems.Minif2f.amc12b_2021_p21

-- Chain `8·log √2 < 2^√2 · log 3` through one rational midpoint:
--   LHS = 4·log 2  <  (13/5)·log 3  ≤  2^√2 · log 3.
-- Sub-goals:
--   • lhs_simp_g_three : LHS = 4·log 2  (log_sqrt + 2^3 = 8).
--   • rational_bound_log : 4·log 2 < (13/5)·log 3  (reduces to 2^20 < 3^13).
--   • pow_sqrt2_lower : 13/5 ≤ 2^√2  (since √2 > log_2(13/5); use 4^√2 ≥ 169/25 via √2 ≥ 7/5).
-- Combinator: a calc using mul_le_mul_of_nonneg_right with log_nonneg.
theorem s9816 :
    (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2) < (2:ℝ)^Real.sqrt 2 * Real.log 3  := by
  have h_lhs_simp : (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2) = 4 * Real.log 2 := lhs_simp_g_three
  have h_rational_bound : 4 * Real.log 2 < (13:ℝ)/5 * Real.log 3 := rational_bound_log
  have h_pow_bound : (13:ℝ)/5 ≤ (2:ℝ)^Real.sqrt 2 := pow_sqrt2_lower
  calc (2:ℝ)^(3:ℝ) * Real.log (Real.sqrt 2)
      = 4 * Real.log 2 := h_lhs_simp
    _ < (13:ℝ)/5 * Real.log 3 := h_rational_bound
    _ ≤ (2:ℝ)^Real.sqrt 2 * Real.log 3 := by
        apply mul_le_mul_of_nonneg_right h_pow_bound
        exact Real.log_nonneg (by norm_num)

end Problems.Minif2f.amc12b_2021_p21
