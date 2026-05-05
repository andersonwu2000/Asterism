import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s119_sub_4 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      0 < (q.1 - p.1)^2 + (q.2 - p.2)^2 := by
  intro P _ _ p _ q _ r _ hpq _ s _ _ _ _ _ _
  by_contra h
  push_neg at h
  have h1 : (q.1 - p.1)^2 ≥ 0 := sq_nonneg _
  have h2 : (q.2 - p.2)^2 ≥ 0 := sq_nonneg _
  have hsq1 : (q.1 - p.1)^2 = 0 := by linarith
  have hsq2 : (q.2 - p.2)^2 = 0 := by linarith
  have hd1 : q.1 - p.1 = 0 := sq_eq_zero_iff.mp hsq1
  have hd2 : q.2 - p.2 = 0 := sq_eq_zero_iff.mp hsq2
  apply hpq
  exact Prod.ext (by linarith) (by linarith)

end Problems.sylvester_gallai
