import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_abel_inv_sq_telescoping_id
import Problems.Minif2f.imo_1978_p5.proofs.L_abel_inv_sq_telescoping_nonneg

namespace Problems.Minif2f.imo_1978_p5

-- Abel summation by parts against weight 1/k² (decreasing in k).
-- (1) `abel_inv_sq_telescoping_id`: pure algebraic identity rewriting the
--     difference ∑ a k / k² - ∑ k / k² as a manifestly-nonneg combination —
--     each weight difference (1/j² - 1/(j+1)²) is multiplied by a prefix sum
--     of (a k - k), plus a boundary term 1/(n+1)² times the total.
-- (2) `abel_inv_sq_telescoping_nonneg`: the RHS of (1) is ≥ 0, using that
--     each prefix sum is ≥ 0 (hypothesis), and each weight-diff > 0.
-- Combinator: `linarith` from the equation + ≥ 0 bound.
theorem s9645 :
    ∀ (n : ℕ) (a : ℕ → ℕ), 0 < n →
    (∀ m, m ≤ n → (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) →
    (∑ k ∈ Finset.Icc 1 n, (k : ℝ) / (k : ℝ)^2) ≤ ∑ k ∈ Finset.Icc 1 n, (a k : ℝ) / (k : ℝ)^2  := by
  intro n a hn h
  have h_id := abel_inv_sq_telescoping_id n a hn h
  have h_nn := abel_inv_sq_telescoping_nonneg n a hn h
  linarith

end Problems.Minif2f.imo_1978_p5
