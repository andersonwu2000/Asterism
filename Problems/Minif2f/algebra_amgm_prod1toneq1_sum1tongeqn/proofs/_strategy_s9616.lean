import Mathlib
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.Defs
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.proofs.L_amgm_uniform_weights

namespace Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn

-- Strategy: weighted AM-GM with uniform weights w_i = 1/n.
-- Sub-goal `amgm_uniform_weights` gives `n * (∏ x)^(1/n) ≤ ∑ x`; rewriting `∏ x = 1`
-- and `1^(1/n) = 1` collapses the LHS to `n`, closing the parent.
theorem s9616 : ∀ (x : ℕ → ℝ) (n : ℕ), 0 < n →
    (∀ i ∈ Finset.range n, 0 ≤ x i) →
    Finset.prod (Finset.range n) x = 1 →
    (n : ℝ) ≤ Finset.sum (Finset.range n) x  := by
  intro x n hn hxn hprod
  have h_amgm := amgm_uniform_weights x n hn hxn hprod
  rw [hprod, Real.one_rpow, mul_one] at h_amgm
  exact h_amgm

end Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
