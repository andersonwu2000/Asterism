import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- abel_inv_sq_telescoping_nonneg: each weight factor (1/j²-1/(j+1)²) ≥ 0
-- and each prefix sum ∑(aₖ-k) ≥ 0 by hypothesis, so every summand is ≥ 0.
theorem abel_inv_sq_telescoping_nonneg :
    ∀ (n : ℕ) (a : ℕ → ℕ), 0 < n →
    (∀ m, m ≤ n → (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) →
    0 ≤ (∑ j ∈ Finset.Icc 1 n,
          (1/(j : ℝ)^2 - 1/((j+1 : ℕ) : ℝ)^2)
            * (∑ k ∈ Finset.Icc 1 j, ((a k : ℝ) - k)))
        + 1/((n+1 : ℕ) : ℝ)^2
            * (∑ k ∈ Finset.Icc 1 n, ((a k : ℝ) - k)) := by
  intro n a hn hm
  apply add_nonneg
  · apply Finset.sum_nonneg
    intro j hj
    rw [Finset.mem_Icc] at hj
    apply mul_nonneg
    · have hj1 : (1 : ℝ) ≤ (j : ℝ) := by exact_mod_cast hj.1
      have hjp : (0 : ℝ) < (j : ℝ) := by linarith
      rw [sub_nonneg]
      apply one_div_le_one_div_of_le (by positivity)
      push_cast
      nlinarith
    · have hsum := hm j hj.2
      have heq : ∑ k ∈ Finset.Icc 1 j, ((a k : ℝ) - k) =
                 ∑ k ∈ Finset.Icc 1 j, (a k : ℝ) - ∑ k ∈ Finset.Icc 1 j, (k : ℝ) := by
        simp [Finset.sum_sub_distrib]
      linarith
  · apply mul_nonneg
    · positivity
    · have hsum := hm n (le_refl n)
      have heq : ∑ k ∈ Finset.Icc 1 n, ((a k : ℝ) - k) =
                 ∑ k ∈ Finset.Icc 1 n, (a k : ℝ) - ∑ k ∈ Finset.Icc 1 n, (k : ℝ) := by
        simp [Finset.sum_sub_distrib]
      linarith

end Problems.Minif2f.imo_1978_p5
