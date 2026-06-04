import Mathlib
import Problems.Minif2f.imo_1978_p5.Defs
import Problems.Minif2f.imo_1978_p5.proofs.L_abel_summation_general_inv_sq

namespace Problems.Minif2f.imo_1978_p5

-- Abel summation identity is purely an algebraic identity over arbitrary
-- `b : ℕ → ℝ`; the integer values of `a` and the dominance hypothesis play no
-- role. Abstract `b k := (a k : ℝ) - k` and reduce to the general identity.
theorem s9727 :
    ∀ (n : ℕ) (a : ℕ → ℕ), 0 < n →
    (∀ m, m ≤ n → (∑ k ∈ Finset.Icc 1 m, (k : ℝ)) ≤ ∑ k ∈ Finset.Icc 1 m, (a k : ℝ)) →
    ∑ k ∈ Finset.Icc 1 n, ((a k : ℝ) - k) / (k : ℝ)^2
    = (∑ j ∈ Finset.Icc 1 n,
        (1/(j : ℝ)^2 - 1/((j+1 : ℕ) : ℝ)^2)
          * (∑ k ∈ Finset.Icc 1 j, ((a k : ℝ) - k)))
      + 1/((n+1 : ℕ) : ℝ)^2
          * (∑ k ∈ Finset.Icc 1 n, ((a k : ℝ) - k))  := by
  intro n a hn hsum
  exact abel_summation_general_inv_sq n (fun k => (a k : ℝ) - k)

end Problems.Minif2f.imo_1978_p5
