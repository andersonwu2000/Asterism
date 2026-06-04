import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_im_le_48_below_97

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce `sum.im ≠ 49` to the strictly-stronger bound `sum.im ≤ 48` on the same
-- range (0 < m < 97). The bound is abstract (single inequality, no equality
-- splits) and is closed via `linarith` with the constant 48 < 49 separation.
theorem s9648 : ∀ (m : ℕ), 0 < m → m < 97 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).im ≠ 49  := by
  intro m hm hmlt heq
  have h_bound := sum_im_le_48_below_97 m hm hmlt
  linarith

end Problems.Minif2f.amc12a_2009_p15
