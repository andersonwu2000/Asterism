import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_abel_summation_inv_sq
import Problems.Minif2f.imo_1978_p5.proofs.L_sum_diff_eq_sum_of_diff

namespace Problems.Minif2f.imo_1978_p5

-- Abel summation by parts against weights 1/k². Split the identity in two:
--   (1) `sum_diff_eq_sum_of_diff` — pure sum_sub_distrib: LHS difference of two
--       sums equals the single sum ∑ ((a k - k)/k²).
--   (2) `abel_summation_inv_sq` — the Abel telescoping itself: rewrite
--       ∑ b(k)/k² (b(k) := a(k) - k) as the weight-difference combination plus
--       the boundary 1/(n+1)² term. Provable by induction on n.
-- Combinator: linarith chains h_sub + h_abel to produce the parent equation.
theorem s9688 :
    ∀ (n : ℕ) (a : ℕ → ℕ), 0 < n →
    (∀ m, m ≤ n → (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) →
    ∑ k ∈ Finset.Icc 1 n, (a k : ℝ) / (k : ℝ)^2
      - ∑ k ∈ Finset.Icc 1 n, (k : ℝ) / (k : ℝ)^2
    = (∑ j ∈ Finset.Icc 1 n,
        (1/(j : ℝ)^2 - 1/((j+1 : ℕ) : ℝ)^2)
          * (∑ k ∈ Finset.Icc 1 j, ((a k : ℝ) - k)))
      + 1/((n+1 : ℕ) : ℝ)^2
          * (∑ k ∈ Finset.Icc 1 n, ((a k : ℝ) - k))  := by
  intro n a hn hsum
  have h_sub := sum_diff_eq_sum_of_diff n a hn hsum
  have h_abel := abel_summation_inv_sq n a hn hsum
  linarith [h_sub, h_abel]
end Problems.Minif2f.imo_1978_p5
