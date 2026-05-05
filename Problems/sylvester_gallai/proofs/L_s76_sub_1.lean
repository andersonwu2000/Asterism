import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s76_sub_1 (L da D2 t : ℝ) :
    t * ((da - L) ^ 2 + D2) + (t - 1) * (L ^ 2 - da ^ 2 - D2) +
    ((1 - t) ^ 2 * L ^ 2 - (da - t * L) ^ 2 - D2) = 0 := by ring

end Problems.sylvester_gallai
