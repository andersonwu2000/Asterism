import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s64_sub_1
import Problems.sylvester_gallai.proofs.L_s64_sub_2

namespace Problems.sylvester_gallai

theorem s64 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    t ≤ 1 / 2 →
    t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ≤
      (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) →
    t < 0 →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c t hncol hL hc1 hc2 hca hcb ht_le hdot ht_neg
  by_cases h : 0 ≤ (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)
  · exact s64_sub_1 p a b c t hncol hL hc1 hc2 hca hcb ht_le hdot ht_neg h
  · push_neg at h
    exact s64_sub_2 p a b c t hncol hL hc1 hc2 hca hcb ht_le hdot ht_neg h

end Problems.sylvester_gallai
