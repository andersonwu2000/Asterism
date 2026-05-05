import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s45_sub_2 : ∀ (p a b : ℝ × ℝ), ¬ Collinear p a b → a ≠ b := by
  intro p a b hnc hab
  apply hnc
  subst hab
  simp [Collinear]

end Problems.sylvester_gallai
