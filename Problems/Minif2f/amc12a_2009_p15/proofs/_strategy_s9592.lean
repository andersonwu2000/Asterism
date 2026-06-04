import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_im_neq_49_below_97

namespace Problems.Minif2f.amc12a_2009_p15

-- Look at imaginary parts: if sum = 48 + 49*I then sum.im = 49. But the imaginary part
-- of the partial sum follows the pattern ±j (j = ⌈m/2⌉), bounded by 48 for m ≤ 96 and
-- only hitting 49 at m = 97. Sub-goal `sum_im_neq_49_below_97` proves sum.im ≠ 49 for
-- m < 97 — a real-valued inequality that avoids reasoning about complex equality.
theorem s9592 : ∀ (m : ℕ), 0 < m → m < 97 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k) ≠ 48 + 49 * Complex.I  := by
  intro m hm hmlt heq
  have h_im_neq := sum_im_neq_49_below_97
  exact h_im_neq m hm hmlt (by rw [heq]; simp)

end Problems.Minif2f.amc12a_2009_p15
