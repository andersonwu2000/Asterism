import Mathlib
import Problems.sylvester_gallai.Defs
namespace Problems.sylvester_gallai

-- on_line_pt_to_off_sq_pos: squared distance from on-line point v to off-line point c is positive
-- v lies on line ab; c does not; so v ≠ c; both coordinate differences zero would force v = c
theorem on_line_pt_to_off_sq_pos :
    ∀ a b v c : ℝ × ℝ, ¬ Collinear a b c → Collinear a b v →
      (v.1 - c.1)^2 + (v.2 - c.2)^2 > 0 := by
  intro a b v c hnc hv
  have hvc : v ≠ c := fun h => hnc (h ▸ hv)
  have hne : (v.1 - c.1)^2 + (v.2 - c.2)^2 ≠ 0 := by
    intro h
    have h1 : v.1 - c.1 = 0 :=
      by nlinarith [sq_nonneg (v.1 - c.1), sq_nonneg (v.2 - c.2)]
    have h2 : v.2 - c.2 = 0 :=
      by nlinarith [sq_nonneg (v.1 - c.1), sq_nonneg (v.2 - c.2)]
    exact hvc (Prod.ext (by linarith) (by linarith))
  have hge : 0 ≤ (v.1 - c.1)^2 + (v.2 - c.2)^2 := by positivity
  exact lt_of_le_of_ne hge (Ne.symm hne)

end Problems.sylvester_gallai
