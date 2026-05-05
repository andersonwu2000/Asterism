import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s113_sub_3 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 →
        (q.1 - p.1)^2 + (q.2 - p.2)^2 > 0 := by
  intro P _ _ p _ q _ r _ hpq _ s _ _ _ _ _ _
  by_contra hcontra
  push_neg at hcontra
  have h1 : (0 : ℝ) ≤ (q.1 - p.1)^2 := sq_nonneg _
  have h2 : (0 : ℝ) ≤ (q.2 - p.2)^2 := sq_nonneg _
  have hx : (q.1 - p.1)^2 = 0 := le_antisymm (by linarith) h1
  have hy : (q.2 - p.2)^2 = 0 := le_antisymm (by linarith) h2
  have hx' : q.1 - p.1 = 0 := sq_eq_zero_iff.mp hx
  have hy' : q.2 - p.2 = 0 := sq_eq_zero_iff.mp hy
  apply hpq
  exact Prod.ext (by linarith) (by linarith)

end Problems.sylvester_gallai
