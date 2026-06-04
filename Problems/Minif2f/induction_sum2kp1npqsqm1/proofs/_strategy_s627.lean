import Mathlib
import Problems.Minif2f.induction_sum2kp1npqsqm1.Defs

namespace Problems.Minif2f.induction_sum2kp1npqsqm1

-- Direct induction on n closes the goal without sub-goals.
-- Base case n=0: empty sum reduces to 0 = (0+1)^2 - 1 = 0 via `simp`.
-- Step case: unfold `Finset.sum_range_succ`, rewrite via IH, normalize the
-- polynomial side with `ring_nf`, then `omega` handles the ℕ truncated
-- subtraction in (n+1)^2 - 1 (safe since (n+1)^2 ≥ 1 for all n : ℕ).
theorem s627 : ∀ (n : ℕ), ∑ k ∈ Finset.range n, (2 * k + 3) = (n + 1) ^ 2 - 1  := by
  intro n
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ, ih]
    ring_nf
    omega

end Problems.Minif2f.induction_sum2kp1npqsqm1
