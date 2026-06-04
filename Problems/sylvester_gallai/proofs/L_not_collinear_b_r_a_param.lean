import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- not_collinear_b_r_a_param: r off line(p,q) and a,b distinct on it implies r not on line(b,a).
-- Factor out (t_b - t_a) from Collinear b r a to derive Collinear p q r, contradicting hncol.
theorem not_collinear_b_r_a_param
    (p q r a b : ℝ × ℝ) (t_a t_b : ℝ)
    (hpq : p ≠ q) (hncol : ¬ Collinear p q r)
    (ha1 : a.1 = p.1 + t_a * (q.1 - p.1))
    (ha2 : a.2 = p.2 + t_a * (q.2 - p.2))
    (hb1 : b.1 = p.1 + t_b * (q.1 - p.1))
    (hb2 : b.2 = p.2 + t_b * (q.2 - p.2))
    (hab : t_a ≠ t_b) :
    ¬ Collinear b r a := by
  intro hcol
  apply hncol
  unfold Collinear at *
  have htab : t_b - t_a ≠ 0 := sub_ne_zero.mpr hab.symm
  have key : (t_b - t_a) * ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1)) = 0 := by
    rw [ha1, ha2, hb1, hb2] at hcol; nlinarith [hcol]
  have hkey2 : (q.1 - p.1) * (r.2 - p.2) = (q.2 - p.2) * (r.1 - p.1) := by
    rcases mul_eq_zero.mp key with h | h
    · exact absurd h htab
    · linarith
  linear_combination hkey2

end Problems.sylvester_gallai
