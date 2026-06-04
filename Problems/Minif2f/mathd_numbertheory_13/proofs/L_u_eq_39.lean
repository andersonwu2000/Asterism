-- Antisymmetry: u = 39 ⇐ (u ≤ 39) ∧ (39 ≤ u), combined by `omega`.
-- Sub 1 (u_le_39): 39 ∈ S (since 14*39 % 100 = 46), so IsLeast gives u ≤ 39.
-- Sub 2 (u_ge_39): u ∈ S so 0 < u and 14*u%100=46; rule out u<39 by case analysis.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs
import Problems.Minif2f.mathd_numbertheory_13.proofs._strategy_s9391

namespace Problems.Minif2f.mathd_numbertheory_13

def u_eq_39 := @Problems.Minif2f.mathd_numbertheory_13.s9391

end Problems.Minif2f.mathd_numbertheory_13
