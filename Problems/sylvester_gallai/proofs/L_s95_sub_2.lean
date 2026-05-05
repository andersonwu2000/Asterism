import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s95_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      (r.1 - p.1)^2 + (r.2 - p.2)^2 > 0 := by
  intro P _ _ p _ q _ r _ _ hncol s _ _ _ _ _ _
  by_contra hle
  push_neg at hle
  apply hncol
  have h1 : (r.1 - p.1)^2 = 0 := by
    nlinarith [sq_nonneg (r.1 - p.1), sq_nonneg (r.2 - p.2)]
  have h2 : (r.2 - p.2)^2 = 0 := by
    nlinarith [sq_nonneg (r.1 - p.1), sq_nonneg (r.2 - p.2)]
  have e1 : r.1 - p.1 = 0 := sq_eq_zero_iff.mp h1
  have e2 : r.2 - p.2 = 0 := sq_eq_zero_iff.mp h2
  have hp1 : p.1 = r.1 := by linarith
  have hp2 : p.2 = r.2 := by linarith
  unfold Collinear
  rw [hp1, hp2]
  ring

end Problems.sylvester_gallai
