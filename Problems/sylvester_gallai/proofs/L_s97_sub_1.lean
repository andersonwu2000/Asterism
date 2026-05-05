import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s97_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
        (s.1 - r.1)^2 + (s.2 - r.2)^2 > 0 := by
  intro P _ _ p _ q _ r _ _hpq hpqr s _ hpqs _ _ _ _
  have hsr : s ≠ r := fun heq => hpqr (heq ▸ hpqs)
  have hcoord : s.1 - r.1 ≠ 0 ∨ s.2 - r.2 ≠ 0 := by
    by_contra h
    push_neg at h
    obtain ⟨h1, h2⟩ := h
    apply hsr
    ext
    · linarith
    · linarith
  rcases hcoord with h | h
  · have h1 : 0 < (s.1 - r.1)^2 := sq_pos_iff.mpr h
    have h2 : 0 ≤ (s.2 - r.2)^2 := sq_nonneg _
    linarith
  · have h1 : 0 ≤ (s.1 - r.1)^2 := sq_nonneg _
    have h2 : 0 < (s.2 - r.2)^2 := sq_pos_iff.mpr h
    linarith

end Problems.sylvester_gallai
