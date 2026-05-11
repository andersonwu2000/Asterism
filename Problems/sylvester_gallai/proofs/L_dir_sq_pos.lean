import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- dir_sq_pos: if a b c are not collinear then the squared length of b-a is positive
-- (i.e. a ≠ b), proved by showing sum-of-squares = 0 forces Collinear a b c via ring.
theorem dir_sq_pos : ∀ a b c : ℝ × ℝ, ¬ Collinear a b c →
    0 < (b.1 - a.1)^2 + (b.2 - a.2)^2 := by
  intro a b c h
  have hnn : 0 ≤ (b.1 - a.1)^2 + (b.2 - a.2)^2 := by positivity
  rcases lt_or_eq_of_le hnn with h' | h'
  · exact h'
  · exfalso
    have heq : (b.1 - a.1)^2 + (b.2 - a.2)^2 = 0 := h'.symm
    have h1 : b.1 - a.1 = 0 := by nlinarith [sq_nonneg (b.1 - a.1), sq_nonneg (b.2 - a.2)]
    have h2 : b.2 - a.2 = 0 := by nlinarith [sq_nonneg (b.1 - a.1), sq_nonneg (b.2 - a.2)]
    apply h
    unfold Collinear
    linear_combination (a.1 - c.1) * h2 - (a.2 - c.2) * h1

end Problems.sylvester_gallai
