import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s52_sub_2 : ∀ (a b : ℝ × ℝ),
    a ≠ b →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 := by
  intro a b hab
  have h : a.1 ≠ b.1 ∨ a.2 ≠ b.2 := by
    by_contra h
    push_neg at h
    exact hab (Prod.ext h.1 h.2)
  rcases h with h1 | h2
  · have hne : b.1 - a.1 ≠ 0 := sub_ne_zero.mpr (Ne.symm h1)
    linarith [sq_pos_of_ne_zero hne, sq_nonneg (b.2 - a.2)]
  · have hne : b.2 - a.2 ≠ 0 := sub_ne_zero.mpr (Ne.symm h2)
    linarith [sq_pos_of_ne_zero hne, sq_nonneg (b.1 - a.1)]

end Problems.sylvester_gallai
