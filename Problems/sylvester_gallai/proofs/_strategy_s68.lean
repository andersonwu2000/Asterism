import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s68_sub_1
import Problems.sylvester_gallai.proofs.L_s68_sub_2

namespace Problems.sylvester_gallai

theorem s68 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    1 / 2 < t →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c t hD hL hc1 hc2 hca hcb ht
  have htne1 : t ≠ 1 := by
    intro h; subst h; apply hcb; ext
    · linarith
    · linarith
  rcases lt_or_gt_of_ne htne1 with h1 | h1
  · exact s68_sub_1 p a b c t hD hL hc1 hc2 hca hcb ht h1
  · exact s68_sub_2 p a b c t hD hL hc1 hc2 hca hcb ht h1

end Problems.sylvester_gallai
