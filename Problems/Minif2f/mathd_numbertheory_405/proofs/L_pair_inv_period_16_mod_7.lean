-- Direct proof: pair-invariant induction. Base case `t 16 % 7 = 0 ∧ t 17 % 7 = 1`
-- unrolls hrec at 2..17 + omega. Inductive step: first conjunct via `ih.2` after
-- a `k+1+16 = k+17` ring rewrite; second uses hrec at `k+18` and `k+2` then
-- `rw [Nat.add_mod, ih.1, ih.2, ← Nat.add_mod]`. Unused `a, h₃` retained per
-- parent signature lock.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_405.Defs
import Problems.Minif2f.mathd_numbertheory_405.proofs._strategy_s9741

namespace Problems.Minif2f.mathd_numbertheory_405

def pair_inv_period_16_mod_7 := @Problems.Minif2f.mathd_numbertheory_405.s9741

end Problems.Minif2f.mathd_numbertheory_405
