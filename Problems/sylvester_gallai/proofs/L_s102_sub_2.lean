import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s102_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 →
        (q.1 - r.1)^2 + (q.2 - r.2)^2 > 0 := by
  intro P _ _ p _ q _ r _ _ hncoll s _ _ _ _ _ _
  by_contra h
  push_neg at h
  have hsq1 : (q.1 - r.1)^2 = 0 := by
    nlinarith [sq_nonneg (q.1 - r.1), sq_nonneg (q.2 - r.2)]
  have hsq2 : (q.2 - r.2)^2 = 0 := by
    nlinarith [sq_nonneg (q.1 - r.1), sq_nonneg (q.2 - r.2)]
  have hx : q.1 - r.1 = 0 := sq_eq_zero_iff.mp hsq1
  have hy : q.2 - r.2 = 0 := sq_eq_zero_iff.mp hsq2
  apply hncoll
  unfold Collinear
  rw [hx, hy]
  ring

end Problems.sylvester_gallai
