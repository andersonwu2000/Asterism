-- Reformulate the negative-divisibility goal as a factorization upper bound.
-- `factorization_three_upper_le` claims v₃(2^n+1) ≤ 1 + v₃(n); pair with
-- `Nat.Prime.pow_dvd_iff_le_factorization` (and the fact that 2^n+1 ≠ 0) to
-- transport into the ¬-divisibility form. The factorization-inequality shape
-- exposes Nat-valued arithmetic suitable for `omega` and recursive bounds on
-- v₃ — cleaner to attack than the contrapositive directly.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9729

namespace Problems.Minif2f.imo_1990_p3

def lte_three_upper_not_dvd := @Problems.Minif2f.imo_1990_p3.s9729

end Problems.Minif2f.imo_1990_p3
