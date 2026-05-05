import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s106_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      ((s.1 - p.1)^2 + (s.2 - p.2)^2) * ((q.1 - p.1)^2 + (q.2 - p.2)^2)
        = ((s.1 - p.1) * (q.1 - p.1) + (s.2 - p.2) * (q.2 - p.2))^2 := by
  intros P _ _ p _ q _ r _ _ _ s _ hcoll _ _ _ _
  unfold Collinear at hcoll
  linear_combination
    ((p.1 - s.1) * (q.2 - s.2) - (p.2 - s.2) * (q.1 - s.1)) * hcoll

end Problems.sylvester_gallai
