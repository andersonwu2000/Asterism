import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- area_sq_pos: non-collinearity implies the signed-area determinant is nonzero,
-- so its square is strictly positive; proved by unfolding Collinear and using
-- linear_combination to transfer the negation, then sq_pos_of_ne_zero.
theorem area_sq_pos : ∀ a b c : ℝ × ℝ, ¬ Collinear a b c →
    0 < ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 := by
  intro a b c h
  unfold Collinear at h
  have hne : (c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1) ≠ 0 := by
    intro heq
    apply h
    linear_combination -heq
  exact sq_pos_of_ne_zero hne

end Problems.sylvester_gallai
