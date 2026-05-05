import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s67_sub_1 (a b x z p : ℝ × ℝ)
    (h_abx : (a.1 - x.1) * (b.2 - x.2) = (a.2 - x.2) * (b.1 - x.1))
    (h_abz : (a.1 - z.1) * (b.2 - z.2) = (a.2 - z.2) * (b.1 - z.1))
    (h_xpz : (x.1 - z.1) * (p.2 - z.2) = (x.2 - z.2) * (p.1 - z.1)) :
    (x.2 - z.2) * ((a.1 - p.1) * (b.2 - p.2) - (a.2 - p.2) * (b.1 - p.1)) = 0 := by
  linear_combination (p.2 - z.2) * h_abx + (x.2 - p.2) * h_abz + (b.2 - a.2) * h_xpz

end Problems.sylvester_gallai
