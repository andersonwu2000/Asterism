import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s49_sub_1 : ∀ (a b c : ℝ × ℝ), ¬ Collinear a b c → b ≠ c := by
  intro a b c h hbc
  subst hbc
  apply h
  unfold Collinear
  ring

end Problems.sylvester_gallai
