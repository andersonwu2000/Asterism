-- Direct pair-invariant induction (mirrors s9741's body, no unused (a, h₃)).
-- Base `t 16 % 7 = 0 ∧ t 17 % 7 = 1` by unrolling hrec at 2..17 + omega.
-- Step: 1st conjunct = ih.2 after `k+1+16 = k+17`; 2nd uses hrec at k+18, k+2
-- then `rw [Nat.add_mod, ih.1, ih.2, ← Nat.add_mod]`.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs._strategy_s9767

namespace Problems.Minif2f.mathd_numbertheory_405

def pair_inv_period_16_17_mod_7 := @Problems.Minif2f.mathd_numbertheory_405.s9767

end Problems.Minif2f.mathd_numbertheory_405
