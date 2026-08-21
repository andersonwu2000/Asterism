import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

theorem main :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      ∃ p ∈ P, ∃ q ∈ P, p ≠ q ∧ ∀ r ∈ P, Collinear p q r → r = p ∨ r = q := by
  sorry

end Problems.sylvester_gallai
