import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s83_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
            ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) ≥ 0 ∨
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
            ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 ∨
        ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
            ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 := by
  intro P _ _ p _ q _ r _ _ _ s _ _ _ _
  set a := (p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)
  set b := (q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)
  set c := (s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)
  rcases le_or_gt 0 a with ha | ha <;>
    rcases le_or_gt 0 b with hb | hb <;>
    rcases le_or_gt 0 c with hc | hc <;>
    first
      | (left; nlinarith)
      | (right; left; nlinarith)
      | (right; right; nlinarith)

end Problems.sylvester_gallai
