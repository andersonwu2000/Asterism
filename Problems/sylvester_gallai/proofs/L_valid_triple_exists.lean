import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- valid_triple_exists: extract a non-collinear triple with p ≠ q from the
-- non-collinearity witness; p = q would make the determinant vanish, so ¬ Collinear
-- forces p ≠ q directly via ring.
theorem valid_triple_exists : ∀ (P : Finset (ℝ × ℝ)),
    (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
    ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r := by
  intro P ⟨a, ha, b, hb, c, hc, habc⟩
  refine ⟨a, ha, b, hb, c, hc, ?_, habc⟩
  intro hab
  apply habc
  unfold Collinear
  rw [hab]
  ring

end Problems.sylvester_gallai
