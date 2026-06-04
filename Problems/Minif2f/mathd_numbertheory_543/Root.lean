-- Reduce ∑_{k ∈ divisors n} 1 to (Nat.divisors n).card, then close 125 - 2 = 123.
-- Single sub-goal: τ(30^4) = 125. Strictly simpler — drops the subtraction and
-- exposes the divisor-count multiplicativity structure (30^4 = 2^4·3^4·5^4, so
-- τ = 5·5·5 = 125) which the Builder closes by prime-power decomposition.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_543.Defs
import Problems.Minif2f.mathd_numbertheory_543.proofs._strategy_s9381

namespace Problems.Minif2f.mathd_numbertheory_543

def main := @Problems.Minif2f.mathd_numbertheory_543.s9381

end Problems.Minif2f.mathd_numbertheory_543
