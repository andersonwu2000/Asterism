import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s64_sub_1 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    t ≤ 1 / 2 →
    t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ≤
      (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) →
    t < 0 →
    0 ≤ (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2) := by
  intro p a b c t hncol hL hc1 hc2 hca hcb ht2 hdot ht hdot_nn
  refine ⟨a, by simp, c, by simp, fun h => hca h.symm, ?_⟩
  -- Show d(a,c)² < d(p,c)²
  have hpa : 0 < (p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2 := by
    by_contra h
    push_neg at h
    have hpa1 : p.1 = a.1 := by nlinarith [sq_nonneg (p.1 - a.1), sq_nonneg (p.2 - a.2)]
    have hpa2 : p.2 = a.2 := by nlinarith [sq_nonneg (p.1 - a.1), sq_nonneg (p.2 - a.2)]
    exact hncol (by rw [hpa1, hpa2]; ring)
  -- d(p,c)² = d(p,a)² + (-2t)·dot + d(a,c)²  (ring identity after substituting c = a + t*(b-a))
  have key : (p.1 - c.1) ^ 2 + (p.2 - c.2) ^ 2 =
             (p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2 +
             (-2 * t) * ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) +
             ((a.1 - c.1) ^ 2 + (a.2 - c.2) ^ 2) := by
    rw [hc1, hc2]; ring
  linarith [mul_nonneg (by linarith : (0 : ℝ) ≤ -2 * t) hdot_nn]

end Problems.sylvester_gallai
