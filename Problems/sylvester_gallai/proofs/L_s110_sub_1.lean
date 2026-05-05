import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s110_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ∀ (X Y : ℝ × ℝ),
        ((X = p ∧ Y = q) ∨ (X = q ∧ Y = p)) →
        ((X.1 - r.1) * (q.1 - p.1) + (X.2 - r.2) * (q.2 - p.2))^2 ≤
            ((Y.1 - r.1) * (q.1 - p.1) + (Y.2 - r.2) * (q.2 - p.2))^2 →
        ((r.1 - Y.1) * (X.2 - Y.2) - (r.2 - Y.2) * (X.1 - Y.1))^2 =
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 := by grind

end Problems.sylvester_gallai
