import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s106_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      (q.1 - p.1)^2 + (q.2 - p.2)^2 > 0 := by
  intro P _ _ p _ q _ r _ hpq _ s _ _ _ _ _ _
  by_contra hle
  push_neg at hle
  apply hpq
  have h1 : (q.1 - p.1)^2 ≥ 0 := sq_nonneg _
  have h2 : (q.2 - p.2)^2 ≥ 0 := sq_nonneg _
  have hx2 : (q.1 - p.1)^2 = 0 := by linarith
  have hy2 : (q.2 - p.2)^2 = 0 := by linarith
  have hx : q.1 - p.1 = 0 := by rwa [sq_eq_zero_iff] at hx2
  have hy : q.2 - p.2 = 0 := by rwa [sq_eq_zero_iff] at hy2
  refine Prod.ext ?_ ?_
  · linarith
  · linarith

end Problems.sylvester_gallai
