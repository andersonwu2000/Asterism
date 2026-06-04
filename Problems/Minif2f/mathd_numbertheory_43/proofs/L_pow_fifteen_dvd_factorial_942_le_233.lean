-- Reduce 15-adic upper bound to 5-adic upper bound via `5 ∣ 15` and `pow_dvd_pow_of_dvd`.
-- v₅(942!) = 188+37+7+1 = 233 is tight (v₃(942!) = 467 is slack), so the 5-adic side
-- exactly captures the bound; one strictly simpler sub-goal on a single prime.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs._strategy_s9613

namespace Problems.Minif2f.mathd_numbertheory_43

def pow_fifteen_dvd_factorial_942_le_233 := @Problems.Minif2f.mathd_numbertheory_43.s9613

end Problems.Minif2f.mathd_numbertheory_43
