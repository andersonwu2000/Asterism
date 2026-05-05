import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s70_sub_1
import Problems.sylvester_gallai.proofs.L_s70_sub_2
import Problems.sylvester_gallai.proofs.L_s70_sub_3

namespace Problems.sylvester_gallai

theorem s70 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    1 / 2 < t →
    1 < t →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c t hcross hL hc1 hc2 hca hcb ht_half ht1
  have hba : b ≠ a := by
    intro h
    simp [h] at hL
  have hdisj := s70_sub_3 p a b c t hcross hL hc1 hc2 hca hcb ht_half ht1
  rcases hdisj with h | h
  · exact s70_sub_1 p a b c hba h
  · exact s70_sub_2 p a b c hcb.symm h

end Problems.sylvester_gallai
