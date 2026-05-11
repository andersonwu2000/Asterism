import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- v_lagrange_id: Lagrange identity for a point collinear with line ab;
-- collinearity makes the cross-product term equal to the area term,
-- reducing LHS - RHS to a multiple of the collinearity determinant.
theorem v_lagrange_id : ∀ a b v c : ℝ × ℝ,
    Collinear a b v →
    ((v.1 - c.1)^2 + (v.2 - c.2)^2) * ((b.1 - a.1)^2 + (b.2 - a.2)^2) =
    ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))^2 +
    ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1))^2 := by
  intro a b v c hcoll
  unfold Collinear at hcoll
  linear_combination -((v.1 - 2*c.1 + a.1) * (b.2 - a.2) -
      (v.2 - 2*c.2 + a.2) * (b.1 - a.1)) * hcoll

end Problems.sylvester_gallai
