import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s63_sub_1 : ∀ (t L dot D : ℝ),
    0 < L →
    D ≠ 0 →
    0 ≤ t →
    t * L ≤ dot →
    t ^ 2 * L ^ 2 < dot ^ 2 + D ^ 2 := by
  intro t L dot D hL hD ht h_dot
  have htL : 0 ≤ t * L := mul_nonneg ht (le_of_lt hL)
  have hD2 : 0 < D ^ 2 := by
    have h : D ^ 2 = D * D := by ring
    rw [h]; exact mul_self_pos.mpr hD
  nlinarith [mul_nonneg (by linarith : 0 ≤ dot - t * L) (by linarith : 0 ≤ dot + t * L)]

end Problems.sylvester_gallai
