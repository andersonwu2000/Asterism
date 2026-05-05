import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s61_sub_1 (a b c w : ℝ × ℝ) :
    Collinear a b c →
    (w = a ∨ w = b ∨ w = c) →
    Collinear a b w := by
  intro h1 h2
  rcases h2 with rfl | rfl | rfl
  · unfold Collinear; ring
  · unfold Collinear; ring
  · exact h1

end Problems.sylvester_gallai
