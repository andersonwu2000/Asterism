import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- line_dir_sq_pos: non-collinearity implies a ≠ b, so squared direction length is positive
-- Strategy: if (b-a) were zero, substituting b=a into the Collinear determinant makes it
-- trivially zero (ring), contradicting ¬ Collinear a b c.
theorem line_dir_sq_pos :
    ∀ a b c : ℝ × ℝ, ¬ Collinear a b c →
      (b.1 - a.1)^2 + (b.2 - a.2)^2 > 0 := by
  intro a b c hnc
  have hnn : 0 ≤ (b.1 - a.1)^2 + (b.2 - a.2)^2 := by positivity
  have hne : (b.1 - a.1)^2 + (b.2 - a.2)^2 ≠ 0 := by
    intro heq
    apply hnc
    unfold Collinear
    have hb1 : b.1 = a.1 := by nlinarith [sq_nonneg (b.1 - a.1), sq_nonneg (b.2 - a.2)]
    have hb2 : b.2 = a.2 := by nlinarith [sq_nonneg (b.1 - a.1), sq_nonneg (b.2 - a.2)]
    rw [hb1, hb2]; ring
  exact lt_of_le_of_ne hnn (Ne.symm hne)

end Problems.sylvester_gallai
