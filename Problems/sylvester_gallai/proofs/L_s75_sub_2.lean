import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s75_sub_2 (p a b c : ℝ × ℝ) (t : ℝ)
    (hc1 : c.1 = a.1 + t * (b.1 - a.1))
    (hc2 : c.2 = a.2 + t * (b.2 - a.2)) :
    ((p.1 - c.1) ^ 2 + (p.2 - c.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
    ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
      t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
    ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 := by
  rw [hc1, hc2]; ring

end Problems.sylvester_gallai
