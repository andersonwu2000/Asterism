import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s72_sub_1 : ∀ (d1 d2 e1 e2 : ℝ),
    (d1 ^ 2 + d2 ^ 2) * (e1 ^ 2 + e2 ^ 2) =
    (d1 * e1 + d2 * e2) ^ 2 + (d1 * e2 - d2 * e1) ^ 2 := by
  intro d1 d2 e1 e2
  ring

end Problems.sylvester_gallai
