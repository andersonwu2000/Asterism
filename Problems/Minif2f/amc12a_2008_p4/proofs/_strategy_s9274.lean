import Mathlib
import Problems.Minif2f.amc12a_2008_p4.Defs
import Problems.Minif2f.amc12a_2008_p4.proofs.L_four_k_telescope_succ
import Problems.Minif2f.amc12a_2008_p4.proofs.L_four_k_telescope_zero

namespace Problems.Minif2f.amc12a_2008_p4

-- Decomposition: induction on `n`.
-- `four_k_telescope_zero` handles the empty product at n=0.
-- `four_k_telescope_succ` extends from n to n+1 given the IH; closes the inductive step.
theorem s9274 :
    ∀ n : ℕ, (∏ k ∈ Finset.Icc (1 : ℕ) n, ((4 : ℝ) * k + 4) / (4 * k)) = (n : ℝ) + 1  := by
  have h_zero := four_k_telescope_zero
  have h_succ := four_k_telescope_succ
  intro n
  induction n with
  | zero => simpa using h_zero
  | succ n ih => simpa using h_succ n ih

end Problems.Minif2f.amc12a_2008_p4
