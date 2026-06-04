import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
-- newnum_sq_factors: ring identity — squared cross-product of parametric points factors as (t_b-t_a)^2 times base numerator squared
theorem newnum_sq_factors
    (p q r a b : ℝ × ℝ) (t_a t_b : ℝ)
    (ha1 : a.1 = p.1 + t_a * (q.1 - p.1))
    (ha2 : a.2 = p.2 + t_a * (q.2 - p.2))
    (hb1 : b.1 = p.1 + t_b * (q.1 - p.1))
    (hb2 : b.2 = p.2 + t_b * (q.2 - p.2)) :
    ((b.1 - a.1) * (r.2 - a.2) - (b.2 - a.2) * (r.1 - a.1)) ^ 2
        = (t_b - t_a) ^ 2
          * ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) ^ 2 := by
  rw [ha1, ha2, hb1, hb2]; ring

end Problems.sylvester_gallai
