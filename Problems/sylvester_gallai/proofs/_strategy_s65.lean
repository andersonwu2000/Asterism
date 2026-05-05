import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s65_sub_1
import Problems.sylvester_gallai.proofs.L_s65_sub_2
import Problems.sylvester_gallai.proofs.L_s65_sub_3
import Problems.sylvester_gallai.proofs.L_s65_sub_4
import Problems.sylvester_gallai.proofs.L_s65_sub_5

namespace Problems.sylvester_gallai

theorem s65 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    t ≤ 1 / 2 →
    (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) <
      t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c t hncol hL hc1 hc2 hca hcb ht hdot
  refine ⟨c, by simp, b, by simp, hcb, ?_⟩
  have h1 := s65_sub_1 p a b
  have h2 := s65_sub_2 a b c t hc1 hc2
  have h3 := s65_sub_3
    ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2))
    ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) t hL hdot ht
  have h4 := s65_sub_4 p a b hncol
  have hkey : ((c.1 - b.1) ^ 2 + (c.2 - b.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) <
              ((p.1 - b.1) ^ 2 + (p.2 - b.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) := by
    nlinarith
  exact s65_sub_5 _ _ _ hL hkey

end Problems.sylvester_gallai
