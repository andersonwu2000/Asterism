import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- tdiff_ba_le_bf_sq: same-side + closer forces (t_b - t_a)^2 ≤ (t_b - t_f)^2
-- Proof: reduce to 2*(t_a-t_f)*(t_b-t_f) ≥ (t_a-t_f)^2; nlinarith via sum/diff squares.
theorem tdiff_ba_le_bf_sq (t_a t_b t_f : ℝ)
    (h_same : (t_a - t_f) * (t_b - t_f) ≥ 0)
    (h_close : (t_a - t_f) ^ 2 ≤ (t_b - t_f) ^ 2) :
    (t_b - t_a) ^ 2 ≤ (t_b - t_f) ^ 2 := by
  nlinarith [sq_nonneg (t_a - t_f + t_b - t_f), sq_nonneg (t_a - t_f - (t_b - t_f)),
             sq_nonneg (t_a - t_f), h_same, h_close]

end Problems.sylvester_gallai
