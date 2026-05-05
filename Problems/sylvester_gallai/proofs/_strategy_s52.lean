import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s52_sub_1
import Problems.sylvester_gallai.proofs.L_s52_sub_2
import Problems.sylvester_gallai.proofs.L_s52_sub_3

namespace Problems.sylvester_gallai

theorem s52 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    ¬ Collinear p a b →
    a ≠ b →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c t hnc hab ht1 ht2 hca hcb
  have hnc_alg : (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) :=
    s52_sub_1 p a b hnc
  have hL : 0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 :=
    s52_sub_2 a b hab
  exact s52_sub_3 p a b c t hnc_alg hL ht1 ht2 hca hcb

end Problems.sylvester_gallai
