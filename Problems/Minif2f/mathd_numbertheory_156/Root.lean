-- Direct: gcd(n+7, 2n+1) divides both n+7 and 2n+1, hence divides 2*(n+7) - (2n+1) = 13.
-- No sub-goals — leaf-bypass: `Nat.dvd_sub` (2-arg version in this toolchain) closes it.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_156.Defs
import Problems.Minif2f.mathd_numbertheory_156.proofs._strategy_s9306

namespace Problems.Minif2f.mathd_numbertheory_156

def main := @Problems.Minif2f.mathd_numbertheory_156.s9306

end Problems.Minif2f.mathd_numbertheory_156
