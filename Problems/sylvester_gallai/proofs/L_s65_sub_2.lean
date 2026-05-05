import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s65_sub_2 : ∀ (a b c : ℝ × ℝ) (t : ℝ),
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    ((c.1 - b.1) ^ 2 + (c.2 - b.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
    (1 - t) ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 := by grind

end Problems.sylvester_gallai
