import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- rb_sq_decomp: |r-b|²·D = cross² + (t_b-t_f)²·D² where D=|q-p|²; Pythagorean decomp along line
theorem rb_sq_decomp
    (p q r b : ℝ × ℝ) (t_b t_f : ℝ)
    (hpq : p ≠ q)
    (hb1 : b.1 = p.1 + t_b * (q.1 - p.1))
    (hb2 : b.2 = p.2 + t_b * (q.2 - p.2))
    (ht_f : t_f = ((r.1 - p.1) * (q.1 - p.1) + (r.2 - p.2) * (q.2 - p.2))
              / ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2)) :
    ((r.1 - b.1) ^ 2 + (r.2 - b.2) ^ 2) * ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2)
        = ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) ^ 2
          + (t_b - t_f) ^ 2 * ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2) ^ 2 := by
  rw [hb1, hb2, ht_f]
  have hD : (q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2 ≠ 0 := by
    intro h
    apply hpq
    ext
    · nlinarith [sq_nonneg (q.1 - p.1), sq_nonneg (q.2 - p.2)]
    · nlinarith [sq_nonneg (q.1 - p.1), sq_nonneg (q.2 - p.2)]
  field_simp [hD]
  ring

end Problems.sylvester_gallai
