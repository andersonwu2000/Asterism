-- Strategy: `Nat.le_induction` on `4 ≤ n` → 2 sub-goals (base + successor step).
-- `h_base` handles n=4 (4²=16, 4!=24) — leaf decide/norm_num.
-- `h_step` is the inductive step `k² ≤ k! → (k+1)² ≤ (k+1)!` for `4 ≤ k`,
-- using `(k+1)! = (k+1)*k!` and `(k+1)² ≤ (k+1)·k²` when `k ≥ 4`.
import Mathlib
import Problems.Minif2f.induction_ineq_nsqlefactn.Defs
import Problems.Minif2f.induction_ineq_nsqlefactn.proofs._strategy_s9298

namespace Problems.Minif2f.induction_ineq_nsqlefactn

def main := @Problems.Minif2f.induction_ineq_nsqlefactn.s9298

end Problems.Minif2f.induction_ineq_nsqlefactn
