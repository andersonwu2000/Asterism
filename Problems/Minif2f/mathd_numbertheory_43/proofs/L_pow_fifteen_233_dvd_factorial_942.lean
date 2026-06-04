-- Decompose 15^233 ∣ 942! via 15 = 3·5 and coprimality of 3^233, 5^233.
-- Sub-goals: 3^233 ∣ 942!  and  5^233 ∣ 942!  — each a single-prime power
-- divisibility (Legendre's formula). Combined by Nat.Coprime.mul_dvd_of_dvd_of_dvd
-- after rewriting 15^233 = 3^233 * 5^233.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_43.Defs
import Problems.Minif2f.mathd_numbertheory_43.proofs._strategy_s9440

namespace Problems.Minif2f.mathd_numbertheory_43

def pow_fifteen_233_dvd_factorial_942 := @Problems.Minif2f.mathd_numbertheory_43.s9440

end Problems.Minif2f.mathd_numbertheory_43
