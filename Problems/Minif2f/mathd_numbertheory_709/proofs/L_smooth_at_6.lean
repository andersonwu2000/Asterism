-- Split into: (A) every divisor of n coprime to 6 must equal 1
-- (the τ(2n)=28 ∧ τ(3n)=30 ⇒ gcd(28,30)=2 ⇒ coprime-to-6 part is τ=1 work);
-- (B) the structural step: a prime p ≠ 2, 3 is coprime to 6, so under (A) it
-- cannot divide n.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs._strategy_s9699

namespace Problems.Minif2f.mathd_numbertheory_709

def smooth_at_6 := @Problems.Minif2f.mathd_numbertheory_709.s9699

end Problems.Minif2f.mathd_numbertheory_709
