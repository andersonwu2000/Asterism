-- Decompose `cube_lte_upper` via `a^3+1 = (a+1)(a^2-a+1)` and 3-adic valuation:
-- v_3(a+1) ≤ k+1 (from ¬3^(k+2) ∣ a+1) and v_3(a^2-a+1) = 1 (from `three_dvd_quad`
-- + new `nine_not_dvd_quad`) force v_3(a^3+1) ≤ k+2, contradicting 3^(k+3) ∣ a^3+1.
-- Sub-goals: re-use existing `cube_factor`, `three_dvd_quad`; introduce
-- `nine_not_dvd_quad`: `3 ∣ a+1` ⟹ `¬ 9 ∣ a^2-a+1` (since `a²-a+1 = 3(3k²-3k+1)`).
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9820

namespace Problems.Minif2f.imo_1990_p3

def cube_lte_upper := @Problems.Minif2f.imo_1990_p3.s9820

end Problems.Minif2f.imo_1990_p3
