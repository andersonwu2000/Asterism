-- Direct proof: 2^n mod 7 cycles through {1,2,4}, so 2^n+1 mod 7 ∈ {2,3,5} ≠ 0.
-- Induct on n to get the invariant; combinator: `omega` finishes from `7 ∣ 2^n+1` + case.
import Mathlib
import Problems.Minif2f.imo_1964_p1_2.Defs
import Problems.Minif2f.imo_1964_p1_2.proofs._strategy_s605

namespace Problems.Minif2f.imo_1964_p1_2

def main := @Problems.Minif2f.imo_1964_p1_2.s605

end Problems.Minif2f.imo_1964_p1_2
