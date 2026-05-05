import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s70_sub_1 : ∀ (p a b c : ℝ × ℝ),
    b ≠ a →
    (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 <
    (p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2 →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2) := by simp_all

end Problems.sylvester_gallai
