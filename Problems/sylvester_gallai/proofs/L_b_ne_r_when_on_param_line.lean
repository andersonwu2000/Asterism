import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- b_ne_r_when_on_param_line: b lies on line(p,q) parametrically; r is off that line,
-- so b = r would force Collinear p q r — contradiction with hncol.
theorem b_ne_r_when_on_param_line
    (p q r b : ℝ × ℝ) (t_b : ℝ)
    (hpq : p ≠ q) (hncol : ¬ Collinear p q r)
    (hb1 : b.1 = p.1 + t_b * (q.1 - p.1))
    (hb2 : b.2 = p.2 + t_b * (q.2 - p.2)) :
    b ≠ r := by
  intro h
  apply hncol
  unfold Collinear
  rw [← h, hb1, hb2]
  ring

end Problems.sylvester_gallai
