import Mathlib
import Problems.Minif2f.induction_ineq_nsqlefactn.Defs

namespace Problems.Minif2f.induction_ineq_nsqlefactn

open Nat in
-- step_succ_sq_le_fact: inductive step — (k+1)^2 ≤ (k+1)! follows from k^2 ≤ k! and 4 ≤ k
-- by factoring (k+1)! = (k+1)*k! and noting k+1 ≤ k^2 ≤ k! when k ≥ 4
theorem step_succ_sq_le_fact : ∀ (k : ℕ), 4 ≤ k → k ^ 2 ≤ k ! → (k + 1) ^ 2 ≤ (k + 1)! := by
  intro k hk ih
  rw [Nat.factorial_succ]
  calc (k + 1) ^ 2 = (k + 1) * (k + 1) := by ring
    _ ≤ (k + 1) * k ! := by
        apply Nat.mul_le_mul_left
        calc k + 1 ≤ k ^ 2 := by nlinarith
          _ ≤ k ! := ih

end Problems.Minif2f.induction_ineq_nsqlefactn
