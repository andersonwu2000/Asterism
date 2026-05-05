import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s117_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ((r.1 - s.1) * (p.2 - s.2) - (r.2 - s.2) * (p.1 - s.1))^2 *
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) =
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
          ((s.1 - p.1)^2 + (s.2 - p.2)^2) := by
  intro P _hexists _hcover p _hp q _hq r _hr _hpq _hncoll s _hs hpqs _hsp _hsq
    _hdotnonneg _hdotsq
  have h : (p.1 - s.1) * (q.2 - s.2) = (p.2 - s.2) * (q.1 - s.1) := hpqs
  linear_combination
    (((r.1 - p.1) ^ 2 - (r.2 - p.2) ^ 2) *
          ((q.1 - p.1) * (s.2 - p.2) + (q.2 - p.2) * (s.1 - p.1))
        + 2 * (r.1 - p.1) * (r.2 - p.2) *
          ((q.2 - p.2) * (s.2 - p.2) - (q.1 - p.1) * (s.1 - p.1))) * h

end Problems.sylvester_gallai
