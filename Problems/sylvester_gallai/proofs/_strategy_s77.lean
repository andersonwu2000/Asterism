import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s77_sub_1
import Problems.sylvester_gallai.proofs.L_s77_sub_2

namespace Problems.sylvester_gallai

theorem s77 : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q  := by
  intro P h_noncol
  by_contra hneg
  exact s77_sub_2 P h_noncol (s77_sub_1 P h_noncol hneg)

end Problems.sylvester_gallai
