import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s120_sub_1 (α β : ℝ) (hαβ : α * β ≥ 0) (hsq : α ^ 2 ≤ β ^ 2) :
    (β - α) ^ 2 ≤ β ^ 2 := by nlinarith

end Problems.sylvester_gallai
