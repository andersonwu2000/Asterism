import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s47_sub_1 (P : Finset (ℝ × ℝ)) (a b r x : ℝ × ℝ)
    (ha : a ∈ P) (hb : b ∈ P) (hr : r ∈ P)
    (hx : x ∈ ({a, b, r} : Finset (ℝ × ℝ))) : x ∈ P := by grind

end Problems.sylvester_gallai
