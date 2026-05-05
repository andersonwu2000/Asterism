import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s78_sub_1
import Problems.sylvester_gallai.proofs.L_s78_sub_2

namespace Problems.sylvester_gallai

theorem s78 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
    False  := by
  intro P h_noncol h_skolem
  exact s78_sub_2 P h_noncol h_skolem (s78_sub_1 P h_noncol h_skolem)

end Problems.sylvester_gallai
