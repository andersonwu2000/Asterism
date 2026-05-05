import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s47_sub_2 (x p z : ℝ × ℝ) (h : ¬ Collinear x p z) : p ≠ z := by
  intro heq
  apply h
  subst heq
  simp [Collinear]

end Problems.sylvester_gallai
