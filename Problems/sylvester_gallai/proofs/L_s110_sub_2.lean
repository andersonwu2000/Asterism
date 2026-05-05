import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s110_sub_2 :
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
        0 < ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 ∧
        0 < (q.1 - p.1)^2 + (q.2 - p.2)^2 := by
  intro P _ _ p _ q _ r _ hpq hncoll s _ _ _ _ _ X Y _ _
  refine ⟨?_, ?_⟩
  · apply sq_pos_of_ne_zero
    intro habs
    apply hncoll
    show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
    linear_combination habs
  · have hne : p.1 ≠ q.1 ∨ p.2 ≠ q.2 := by
      by_contra h
      push_neg at h
      exact hpq (Prod.ext h.1 h.2)
    rcases hne with h | h
    · have hs : q.1 - p.1 ≠ 0 := sub_ne_zero.mpr (Ne.symm h)
      have hsq : 0 < (q.1 - p.1)^2 := sq_pos_of_ne_zero hs
      nlinarith [sq_nonneg (q.2 - p.2)]
    · have hs : q.2 - p.2 ≠ 0 := sub_ne_zero.mpr (Ne.symm h)
      have hsq : 0 < (q.2 - p.2)^2 := sq_pos_of_ne_zero hs
      nlinarith [sq_nonneg (q.1 - p.1)]

end Problems.sylvester_gallai
