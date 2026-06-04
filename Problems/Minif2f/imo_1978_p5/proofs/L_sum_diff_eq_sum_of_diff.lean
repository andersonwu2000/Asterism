import Mathlib
namespace Problems.Minif2f.imo_1978_p5

-- sum_diff_eq_sum_of_diff: Finset.sum_sub_distrib + ← sub_div collapses
-- the difference of two sums into a single sum of pointwise differences.
theorem sum_diff_eq_sum_of_diff :
    ∀ (n : ℕ) (a : ℕ → ℕ), 0 < n →
    (∀ m, m ≤ n → (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) →
    ∑ k ∈ Finset.Icc 1 n, (a k : ℝ) / (k : ℝ)^2
      - ∑ k ∈ Finset.Icc 1 n, (k : ℝ) / (k : ℝ)^2
    = ∑ k ∈ Finset.Icc 1 n, ((a k : ℝ) - k) / (k : ℝ)^2 := by
  intro n a hn h
  simp only [← Finset.sum_sub_distrib, ← sub_div]

end Problems.Minif2f.imo_1978_p5
