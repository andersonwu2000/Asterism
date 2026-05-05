import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s116_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 →
      ((q.1 - r.1) * (s.2 - r.2) - (q.2 - r.2) * (s.1 - r.1)) *
            ((q.1 - p.1)^2 + (q.2 - p.2)^2) =
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1)) *
            (((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) -
              ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))) →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 +
            ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 =
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) *
            ((q.1 - r.1)^2 + (q.2 - r.2)^2) →
      (q.1 - p.1)^2 + (q.2 - p.2)^2 > 0 →
      (q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1) ≠ 0 →
      (((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) -
            ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 +
            ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 := by
  intro P _ _ p _ q _ r _ _ _ s _ _ _ _ hαβ hβsq _ _ _ hB
  -- Reduce to a 3-variable scalar inequality using a helper lemma.
  suffices h : ∀ (a b c : ℝ), a * b ≥ 0 → b^2 < a^2 → c ≠ 0 →
      (b - a)^2 < a^2 + c^2 by
    exact h _ _ _ hαβ hβsq hB
  intro a b c hab hba hc
  have hc2 : 0 < c^2 := sq_pos_of_ne_zero hc
  have h_sq_sq : (b^2)^2 ≤ (a * b)^2 := by nlinarith [sq_nonneg b, hba]
  have key : b^2 ≤ a * b := (sq_le_sq₀ (sq_nonneg b) hab).mp h_sq_sq
  nlinarith [key, sq_nonneg b, hc2]

end Problems.sylvester_gallai
