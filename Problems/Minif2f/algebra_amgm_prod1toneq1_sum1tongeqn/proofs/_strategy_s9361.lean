import Mathlib
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.Defs
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.proofs.L_amgm_real_prod_one_pos

namespace Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn

-- Case-split on n: n=0 is degenerate (∑ over empty = 0 ≥ 0 = ↑0);
-- n≥1 is the substantive AM-GM with prod=1, abstracted as `amgm_real_prod_one_pos`.
theorem s9361 : ∀ (x : ℕ → ℝ) (n : ℕ),
    (∀ i ∈ Finset.range n, 0 ≤ x i) →
    Finset.prod (Finset.range n) x = 1 →
    (n : ℝ) ≤ Finset.sum (Finset.range n) x  := by
  intro x n hx hprod
  rcases Nat.eq_zero_or_pos n with hn | hn
  · subst hn
    simp
  · exact amgm_real_prod_one_pos x n hn hx hprod

end Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
