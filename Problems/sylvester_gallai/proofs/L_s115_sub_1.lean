import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s115_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ∀ (μ : ℝ),
      s.1 - q.1 = μ * (p.1 - q.1) →
      s.2 - q.2 = μ * (p.2 - q.2) →
      (q.1 - r.1)^2 + (q.2 - r.2)^2 > 0 →
      ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 > 0 := by
  intro P _ _ p _ q _ r _ _ hncolr s _ _ _ _ _ _ μ _ _ _
  apply sq_pos_of_ne_zero
  intro h
  apply hncolr
  show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
  linear_combination h

end Problems.sylvester_gallai
