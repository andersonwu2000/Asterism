import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s45_sub_3 : ∀ (a b : ℝ × ℝ), a ≠ b →
    0 < (a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2 := by
  intro a b hab
  have hne : a.1 ≠ b.1 ∨ a.2 ≠ b.2 := by
    rwa [ne_eq, Prod.ext_iff, not_and_or] at hab
  rcases hne with h | h
  · have h1 : (a.1 - b.1) ≠ 0 := sub_ne_zero.mpr h
    linarith [sq_pos_of_ne_zero h1, sq_nonneg (a.2 - b.2)]
  · have h1 : (a.2 - b.2) ≠ 0 := sub_ne_zero.mpr h
    linarith [sq_pos_of_ne_zero h1, sq_nonneg (a.1 - b.1)]

end Problems.sylvester_gallai
