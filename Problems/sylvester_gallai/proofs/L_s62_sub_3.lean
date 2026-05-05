import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s62_sub_3 (a b p : ℝ × ℝ) :
    Collinear a b p →
    Collinear p a b := by
  simp only [Collinear]
  intro h
  linear_combination h

end Problems.sylvester_gallai
