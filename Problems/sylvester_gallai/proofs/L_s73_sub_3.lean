import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s73_sub_3 : ∀ (p a b c : ℝ × ℝ),
    Collinear a b c →
    a ≠ b →
    ((c.1 - c.1) * (p.2 - c.2) - (c.2 - c.2) * (p.1 - c.1)) ^ 2 *
    ((a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2) =
    ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 *
    ((c.1 - c.1) ^ 2 + (c.2 - c.2) ^ 2) := by norm_num

end Problems.sylvester_gallai
