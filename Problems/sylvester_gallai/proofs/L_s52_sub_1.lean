import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s52_sub_1 : ∀ (p a b : ℝ × ℝ),
    ¬ Collinear p a b →
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) := by tauto

end Problems.sylvester_gallai
