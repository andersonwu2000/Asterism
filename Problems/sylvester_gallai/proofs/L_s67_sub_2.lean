import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s67_sub_2 (a b x z p : ℝ × ℝ)
    (h_x2z2 : x.2 ≠ z.2)
    (h_prod : (x.2 - z.2) * ((a.1 - p.1) * (b.2 - p.2) - (a.2 - p.2) * (b.1 - p.1)) = 0) :
    (a.1 - p.1) * (b.2 - p.2) = (a.2 - p.2) * (b.1 - p.1) := by
  have hd : x.2 - z.2 ≠ 0 := sub_ne_zero.mpr h_x2z2
  have hG : (a.1 - p.1) * (b.2 - p.2) - (a.2 - p.2) * (b.1 - p.1) = 0 :=
    (mul_eq_zero.mp h_prod).resolve_left hd
  linarith

end Problems.sylvester_gallai
