import Mathlib
import Problems.Minif2f.induction_ineq_nsqlefactn.Defs
import Problems.Minif2f.induction_ineq_nsqlefactn.proofs.L_base_four_sq_le_fact
import Problems.Minif2f.induction_ineq_nsqlefactn.proofs.L_step_succ_sq_le_fact

namespace Problems.Minif2f.induction_ineq_nsqlefactn

-- Strategy: `Nat.le_induction` on `4 ≤ n` → 2 sub-goals (base + successor step).
-- `h_base` handles n=4 (4²=16, 4!=24) — leaf decide/norm_num.
-- `h_step` is the inductive step `k² ≤ k! → (k+1)² ≤ (k+1)!` for `4 ≤ k`,
-- using `(k+1)! = (k+1)*k!` and `(k+1)² ≤ (k+1)·k²` when `k ≥ 4`.
open Nat in
theorem s9298 : ∀ (n : ℕ) (h₀ : 4 ≤ n), n ^ 2 ≤ n !  := by
  intro n h₀
  have h_base := base_four_sq_le_fact
  have h_step := step_succ_sq_le_fact
  induction n, h₀ using Nat.le_induction with
  | base => exact h_base
  | succ k hk ih => exact h_step k hk ih

end Problems.Minif2f.induction_ineq_nsqlefactn
