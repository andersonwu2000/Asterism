import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s51_sub_1
import Problems.sylvester_gallai.proofs.L_s51_sub_2

namespace Problems.sylvester_gallai

theorem s51 : ∀ (p a b c : ℝ × ℝ),
    ¬ Collinear p a b →
    Collinear a b c →
    a ≠ b → c ≠ a → c ≠ b →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c hnc hcol hab hca hcb
  obtain ⟨t, ht1, ht2⟩ := s51_sub_1 a b c hab hcol
  exact s51_sub_2 p a b c t hnc hab ht1 ht2 hca hcb

end Problems.sylvester_gallai
