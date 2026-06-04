import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_abel_inv_sq_succ_step

namespace Problems.Minif2f.imo_1978_p5

-- Abel summation identity for arbitrary `b : ℕ → ℝ` against weights 1/k²,
-- by induction on n. Base case (n=0) collapses both sides to 0; step adds
-- b(n+1)/(n+1)² to LHS while RHS difference simplifies via S_{n+1} = S_n + b(n+1).
theorem s9762 :
    ∀ (n : ℕ) (b : ℕ → ℝ),
    ∑ k ∈ Finset.Icc 1 n, b k / (k : ℝ)^2
    = (∑ j ∈ Finset.Icc 1 n,
        (1/(j : ℝ)^2 - 1/((j+1 : ℕ) : ℝ)^2)
          * (∑ k ∈ Finset.Icc 1 j, b k))
      + 1/((n+1 : ℕ) : ℝ)^2
          * (∑ k ∈ Finset.Icc 1 n, b k)  := by
  intro n b
  induction n with
  | zero => simp
  | succ n ih => exact abel_inv_sq_succ_step n b ih

end Problems.Minif2f.imo_1978_p5
