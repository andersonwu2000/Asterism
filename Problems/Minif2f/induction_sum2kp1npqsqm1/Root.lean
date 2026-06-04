-- Direct induction on n closes the goal without sub-goals.
-- Base case n=0: empty sum reduces to 0 = (0+1)^2 - 1 = 0 via `simp`.
-- Step case: unfold `Finset.sum_range_succ`, rewrite via IH, normalize the
-- polynomial side with `ring_nf`, then `omega` handles the ℕ truncated
-- subtraction in (n+1)^2 - 1 (safe since (n+1)^2 ≥ 1 for all n : ℕ).
import Mathlib
import Problems.Minif2f.induction_sum2kp1npqsqm1.Defs
import Problems.Minif2f.induction_sum2kp1npqsqm1.proofs._strategy_s627

namespace Problems.Minif2f.induction_sum2kp1npqsqm1

def main := @Problems.Minif2f.induction_sum2kp1npqsqm1.s627

end Problems.Minif2f.induction_sum2kp1npqsqm1
