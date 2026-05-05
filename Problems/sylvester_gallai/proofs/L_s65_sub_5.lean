import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s65_sub_5 : ∀ (A B L : ℝ), 0 < L → A * L < B * L → A < B := by simp_all

end Problems.sylvester_gallai
