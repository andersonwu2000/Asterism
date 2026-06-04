-- Induction on k. Base case (k=0) reduces to 3 ∣ 2^m + 1 (m odd).
-- Inductive step: from 3^(k+1) ∣ 2^(3^k*m)+1, lift to 3^(k+2) ∣ 2^(3^(k+1)*m)+1
-- via the factorization a^3 + 1 = (a+1)(a^2 - a + 1) with 3 ∣ a^2 - a + 1.
import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs._strategy_s9765

namespace Problems.Minif2f.imo_1990_p3

def three_lte_lifting := @Problems.Minif2f.imo_1990_p3.s9765

end Problems.Minif2f.imo_1990_p3
