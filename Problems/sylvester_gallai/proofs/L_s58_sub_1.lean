import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s58_sub_1 (a b c x : ℝ × ℝ) :
    x ∈ ({a, b, c} : Finset (ℝ × ℝ)) → x = a ∨ x = b ∨ x = c := by norm_num

end Problems.sylvester_gallai
