-- Chain `8·log √2 < 2^√2 · log 3` through one rational midpoint:
--   LHS = 4·log 2  <  (13/5)·log 3  ≤  2^√2 · log 3.
-- Sub-goals:
--   • lhs_simp_g_three : LHS = 4·log 2  (log_sqrt + 2^3 = 8).
--   • rational_bound_log : 4·log 2 < (13/5)·log 3  (reduces to 2^20 < 3^13).
--   • pow_sqrt2_lower : 13/5 ≤ 2^√2  (since √2 > log_2(13/5); use 4^√2 ≥ 169/25 via √2 ≥ 7/5).
-- Combinator: a calc using mul_le_mul_of_nonneg_right with log_nonneg.
import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs._strategy_s9816

namespace Problems.Minif2f.amc12b_2021_p21

def g_three_pos := @Problems.Minif2f.amc12b_2021_p21.s9816

end Problems.Minif2f.amc12b_2021_p21
