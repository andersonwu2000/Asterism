import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- cross_eq_factor_id: cross-product · |d|² = signed-area · (proj_u − proj_v) for collinear u, v
-- Identity X·D = A·(pu−pv) proved by linear_combination with coefficients −pv·hu + pu·hv,
-- derived from the parametric fact that collinear u=a+t·d, v=a+s·d gives X=(t−s)·A, pu−pv=(t−s)·D.
theorem cross_eq_factor_id : ∀ a b u v c : ℝ × ℝ,
    Collinear a b u → Collinear a b v →
    ((u.1 - c.1) * (v.2 - c.2) - (u.2 - c.2) * (v.1 - c.1)) *
        ((b.1 - a.1)^2 + (b.2 - a.2)^2) =
    ((c.1 - a.1) * (b.2 - a.2) - (c.2 - a.2) * (b.1 - a.1)) *
        (((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) -
         ((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2))) := by
  intro a b u v c hu hv
  unfold Collinear at hu hv
  linear_combination -((v.1 - c.1) * (b.1 - a.1) + (v.2 - c.2) * (b.2 - a.2)) * hu +
    ((u.1 - c.1) * (b.1 - a.1) + (u.2 - c.2) * (b.2 - a.2)) * hv

end Problems.sylvester_gallai
