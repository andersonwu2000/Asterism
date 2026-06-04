import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_abel_inv_sq_inequality
import Problems.Minif2f.imo_1978_p5.proofs.L_sum_k_div_ksq_eq_sum_one_div_k

namespace Problems.Minif2f.imo_1978_p5

-- Split the conclusion at the `1/k = k/k²` rewrite (a Builder leaf) before
-- invoking a pure Abel summation inequality against weight `1/k²` (Backward)
-- that consumes the prefix-sum bound. `linarith` closes from the equality + ≤.
theorem s9492 :
    ∀ (n : ℕ) (a : ℕ → ℕ), 0 < n →
    (∀ m, m ≤ n → (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) →
    (∑ k ∈ Finset.Icc 1 n, (1 : ℝ) / k) ≤ ∑ k ∈ Finset.Icc 1 n, (a k : ℝ) / k ^ 2  := by
  intro n a hn hprefix
  have h_abel := abel_inv_sq_inequality n a hn hprefix
  have h_rewrite := sum_k_div_ksq_eq_sum_one_div_k n a hn hprefix
  linarith

end Problems.Minif2f.imo_1978_p5
