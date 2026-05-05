import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s79_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∃ p ∈ P, ∃ q ∈ P, ∃ r ∈ P, p ≠ q ∧ ¬ Collinear p q r := by
  intro P h_noncol _
  obtain ⟨a, ha, b, hb, c, hc, hncol⟩ := h_noncol
  refine ⟨a, ha, b, hb, c, hc, ?_, hncol⟩
  rintro rfl
  apply hncol
  unfold Collinear
  ring

end Problems.sylvester_gallai
