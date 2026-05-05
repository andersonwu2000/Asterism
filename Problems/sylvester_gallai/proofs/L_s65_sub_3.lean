import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s65_sub_3 : ∀ (dot L t : ℝ),
    0 < L →
    dot < t * L →
    t ≤ 1 / 2 →
    (1 - t) ^ 2 * L ^ 2 < (dot - L) ^ 2 := by
  intro dot L t hL hdot ht
  have h1 : 0 < t * L - dot := by linarith
  have h2 : 0 < (2 - t) * L - dot := by nlinarith
  nlinarith [mul_pos h1 h2]

end Problems.sylvester_gallai
