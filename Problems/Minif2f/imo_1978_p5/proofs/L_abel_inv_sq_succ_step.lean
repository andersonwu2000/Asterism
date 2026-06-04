import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs

namespace Problems.Minif2f.imo_1978_p5

-- abel_inv_sq_succ_step: inductive step for Abel summation identity (splitting Icc and ring)
theorem abel_inv_sq_succ_step :
    ∀ (n : ℕ) (b : ℕ → ℝ),
      (∑ k ∈ Finset.Icc 1 n, b k / (k : ℝ)^2
        = (∑ j ∈ Finset.Icc 1 n,
            (1/(j : ℝ)^2 - 1/((j+1 : ℕ) : ℝ)^2)
              * (∑ k ∈ Finset.Icc 1 j, b k))
          + 1/((n+1 : ℕ) : ℝ)^2
              * (∑ k ∈ Finset.Icc 1 n, b k)) →
      (∑ k ∈ Finset.Icc 1 (n+1), b k / (k : ℝ)^2
        = (∑ j ∈ Finset.Icc 1 (n+1),
            (1/(j : ℝ)^2 - 1/((j+1 : ℕ) : ℝ)^2)
              * (∑ k ∈ Finset.Icc 1 j, b k))
          + 1/((n+1+1 : ℕ) : ℝ)^2
              * (∑ k ∈ Finset.Icc 1 (n+1), b k)) := by
  intro n b ih
  have hmem : (n+1) ∉ Finset.Icc 1 n := by simp [Finset.mem_Icc]
  have hIcc : Finset.Icc 1 (n+1) = insert (n+1) (Finset.Icc 1 n) := by
    ext x; simp [Finset.mem_Icc]; omega
  have split : ∀ (f : ℕ → ℝ), ∑ k ∈ Finset.Icc 1 (n+1), f k =
      (∑ k ∈ Finset.Icc 1 n, f k) + f (n+1) := by
    intro f
    have hrw : (∑ k ∈ Finset.Icc 1 n, f k) + f (n+1) =
        f (n+1) + ∑ k ∈ Finset.Icc 1 n, f k := by ring
    rw [hrw, hIcc, Finset.sum_insert hmem]
  have sn_eq : ∑ k ∈ Finset.Icc 1 (n+1), b k =
      (∑ k ∈ Finset.Icc 1 n, b k) + b (n+1) := split b
  rw [split (fun k => b k / (k : ℝ)^2),
      split (fun j => (1/(j : ℝ)^2 - 1/((j+1 : ℕ) : ℝ)^2) * ∑ k ∈ Finset.Icc 1 j, b k),
      sn_eq]
  have h1 : (1 / ((n+1 : ℕ) : ℝ)^2 - 1 / ((n+1+1 : ℕ) : ℝ)^2) *
      ((∑ k ∈ Finset.Icc 1 n, b k) + b (n+1)) +
      1 / ((n+1+1 : ℕ) : ℝ)^2 * ((∑ k ∈ Finset.Icc 1 n, b k) + b (n+1)) =
      1 / ((n+1 : ℕ) : ℝ)^2 * (∑ k ∈ Finset.Icc 1 n, b k) +
      b (n+1) / ((n+1 : ℕ) : ℝ)^2 := by ring
  linarith [ih, h1]

end Problems.Minif2f.imo_1978_p5
