import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- det_sq_pos_of_not_collinear: sq_pos_of_ne_zero on the determinant, nonzero by hncol.
-- entry_kind: Builder
theorem det_sq_pos_of_not_collinear
    (p q r : ℝ × ℝ) (hncol : ¬ Collinear p q r) :
    0 < ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) ^ 2 := by
  unfold Collinear at hncol
  have hD : (p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1) ≠ 0 := sub_ne_zero.mpr hncol
  exact sq_pos_of_ne_zero hD

end Problems.sylvester_gallai
