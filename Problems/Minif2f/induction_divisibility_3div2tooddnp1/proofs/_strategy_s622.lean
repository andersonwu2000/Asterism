import Mathlib
import Problems.Minif2f.induction_divisibility_3div2tooddnp1.Defs
import Problems.Minif2f.induction_divisibility_3div2tooddnp1.proofs.L_base_case
import Problems.Minif2f.induction_divisibility_3div2tooddnp1.proofs.L_inductive_step

namespace Problems.Minif2f.induction_divisibility_3div2tooddnp1

-- Induction on n: base case at n=0 plus an inductive step k → k+1.
-- The combinator is `Nat.rec` (via `induction n`), threading the per-step
-- divisibility implication over the predecessor's witness.
theorem s622 : ∀ (n : ℕ), 3 ∣ 2 ^ (2 * n + 1) + 1  := by
  intro n
  have h_base := base_case
  have h_step := inductive_step
  induction n with
  | zero => exact h_base
  | succ k ih => exact h_step k ih

end Problems.Minif2f.induction_divisibility_3div2tooddnp1
