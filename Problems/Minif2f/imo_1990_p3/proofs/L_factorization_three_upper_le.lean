-- Decompose n = 3^k · m with k = v₃(n), m = n / 3^k. Then m is odd and 3 ∤ m.
-- Reduces the factorization upper bound v₃(2^n+1) ≤ 1 + v₃(n) to the prime-3 LTE
-- upper bound `three_lte_upper_lifting`: ¬ 3^(k+2) ∣ 2^(3^k·m)+1 for m odd, 3∤m.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9764

namespace Problems.Minif2f.imo_1990_p3

def factorization_three_upper_le := @Problems.Minif2f.imo_1990_p3.s9764

end Problems.Minif2f.imo_1990_p3
