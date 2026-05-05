import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s65_sub_4 : ∀ (p a b : ℝ × ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < ((p.1 - b.1) * (b.2 - a.2) - (p.2 - b.2) * (b.1 - a.1)) ^ 2 := by
  intro p a b h
  apply sq_pos_of_ne_zero
  intro heq
  apply h
  linear_combination -heq

end Problems.sylvester_gallai
