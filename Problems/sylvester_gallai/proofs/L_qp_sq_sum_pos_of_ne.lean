import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
-- qp_sq_sum_pos_of_ne: sq_pos + linarith; split on which coordinate differs to get a positive square
theorem qp_sq_sum_pos_of_ne (p q : ℝ × ℝ) (hpq : p ≠ q) :
    0 < (q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2 := by
  have h : p.1 ≠ q.1 ∨ p.2 ≠ q.2 := by
    by_contra h; push Not at h; exact hpq (Prod.ext h.1 h.2)
  rcases h with h1 | h2
  · have h1' : q.1 - p.1 ≠ 0 := sub_ne_zero.mpr (Ne.symm h1)
    have hpos : 0 < (q.1 - p.1) ^ 2 := by positivity
    linarith [sq_nonneg (q.2 - p.2)]
  · have h2' : q.2 - p.2 ≠ 0 := sub_ne_zero.mpr (Ne.symm h2)
    have hpos : 0 < (q.2 - p.2) ^ 2 := by positivity
    linarith [sq_nonneg (q.1 - p.1)]

end Problems.sylvester_gallai
