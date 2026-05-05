import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s59_sub_1
import Problems.sylvester_gallai.proofs.L_s59_sub_2
import Problems.sylvester_gallai.proofs.L_s59_sub_3

namespace Problems.sylvester_gallai

theorem s59 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    t ≤ 1 / 2 →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c t hD hL hc1 hc2 hca hcb htl
  by_cases h_dot : (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) <
      t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)
  · exact s59_sub_1 p a b c t hD hL hc1 hc2 hca hcb htl h_dot
  · push_neg at h_dot
    by_cases h_t : 0 ≤ t
    · exact s59_sub_2 p a b c t hD hL hc1 hc2 hca hcb htl h_dot h_t
    · push_neg at h_t
      exact s59_sub_3 p a b c t hD hL hc1 hc2 hca hcb htl h_dot h_t

end Problems.sylvester_gallai
