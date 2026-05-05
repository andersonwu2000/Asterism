import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s112_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      (q.1 - r.1)^2 + (q.2 - r.2)^2 > 0 := by
  intro P _ _ p _ q _ r _ _ hNC s _ _ _ _ _ _
  by_contra hle
  push_neg at hle
  have hq1sq : (q.1 - r.1)^2 = 0 := by
    nlinarith [sq_nonneg (q.1 - r.1), sq_nonneg (q.2 - r.2)]
  have hq2sq : (q.2 - r.2)^2 = 0 := by
    nlinarith [sq_nonneg (q.1 - r.1), sq_nonneg (q.2 - r.2)]
  have hq1 : q.1 - r.1 = 0 := sq_eq_zero_iff.mp hq1sq
  have hq2 : q.2 - r.2 = 0 := sq_eq_zero_iff.mp hq2sq
  apply hNC
  show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
  rw [hq1, hq2]
  ring

end Problems.sylvester_gallai
