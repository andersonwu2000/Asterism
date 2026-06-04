import Mathlib
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.Defs
import Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn.proofs.L_geom_le_arith_mean_avg

namespace Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn

-- AM-GM with uniform weights. Sub-goal `geom_le_arith_mean_avg` provides the
-- average form `(∏ x)^(1/n) ≤ (1/n) * ∑ x`; we multiply both sides by `n > 0`,
-- the `n * (1/n)` cancels, yielding `n * (∏ x)^(1/n) ≤ ∑ x`. The `∏ x = 1`
-- hypothesis is unused at this level; it lives at the parent.
theorem s9658 : ∀ (x : ℕ → ℝ) (n : ℕ), 0 < n →
    (∀ i ∈ Finset.range n, 0 ≤ x i) →
    Finset.prod (Finset.range n) x = 1 →
    (n : ℝ) * (∏ i ∈ Finset.range n, x i)^((1:ℝ)/n)
      ≤ ∑ i ∈ Finset.range n, x i  := by
  intro x n hn hnn hprod
  have h_avg := geom_le_arith_mean_avg x n hn hnn hprod
  have hn_pos : (0:ℝ) < n := by exact_mod_cast hn
  have hn_ne : (n : ℝ) ≠ 0 := ne_of_gt hn_pos
  have h2 := mul_le_mul_of_nonneg_left h_avg hn_pos.le
  have hcancel : (n:ℝ) * ((1/(n:ℝ)) * ∑ i ∈ Finset.range n, x i)
        = ∑ i ∈ Finset.range n, x i := by
    field_simp
  linarith

end Problems.Minif2f.algebra_amgm_prod1toneq1_sum1tongeqn
