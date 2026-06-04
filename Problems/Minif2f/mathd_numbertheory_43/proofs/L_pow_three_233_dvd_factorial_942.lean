-- Reduce `3^233 ∣ 942!` to a factorization lower bound via Legendre's formula:
-- `Nat.Prime.pow_dvd_iff_le_factorization` converts `p^k ∣ n!` to
-- `k ≤ n!.factorization p`. v₃(942!) = 467, so 233 is well below the tight bound;
-- the remaining sub-goal is a pure numerical valuation computation.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs._strategy_s9626

namespace Problems.Minif2f.mathd_numbertheory_43

def pow_three_233_dvd_factorial_942 := @Problems.Minif2f.mathd_numbertheory_43.s9626

end Problems.Minif2f.mathd_numbertheory_43
