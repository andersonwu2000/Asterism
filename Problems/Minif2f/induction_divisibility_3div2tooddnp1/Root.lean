-- Induction on n: base case at n=0 plus an inductive step k → k+1.
-- The combinator is `Nat.rec` (via `induction n`), threading the per-step
-- divisibility implication over the predecessor's witness.
import Mathlib
import Problems.Minif2f.induction_divisibility_3div2tooddnp1.Defs
import Problems.Minif2f.induction_divisibility_3div2tooddnp1.proofs._strategy_s622

namespace Problems.Minif2f.induction_divisibility_3div2tooddnp1

def main := @Problems.Minif2f.induction_divisibility_3div2tooddnp1.s622

end Problems.Minif2f.induction_divisibility_3div2tooddnp1
