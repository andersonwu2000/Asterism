import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_strict_gt_on_sqrt2_three

namespace Problems.Minif2f.amc12b_2021_p21

-- Reduce disequality to strict comparison: show `√2^(2^y) < y^(2^√2)` on (√2, 3]
-- and close `≠` via `ne_of_gt`. The single sub-goal is strictly simpler than the
-- parent: a one-sided strict inequality instead of disequality, same hypothesis set.
theorem s9746 : ∀ y : ℝ, 0 < y → Real.sqrt 2 < y → y ≤ 3 →
    y ^ (2 : ℝ) ^ Real.sqrt 2 ≠ Real.sqrt 2 ^ (2 : ℝ) ^ y  := by
  intro y hy_pos hy_lo hy_hi
  have h_strict := strict_gt_on_sqrt2_three y hy_pos hy_lo hy_hi
  exact (ne_of_gt h_strict)

end Problems.Minif2f.amc12b_2021_p21
