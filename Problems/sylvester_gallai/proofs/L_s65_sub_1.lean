import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s65_sub_1 : ∀ (p a b : ℝ × ℝ),
    ((p.1 - b.1) ^ 2 + (p.2 - b.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
    ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
      ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
    ((p.1 - b.1) * (b.2 - a.2) - (p.2 - b.2) * (b.1 - a.1)) ^ 2 := by grind

end Problems.sylvester_gallai
