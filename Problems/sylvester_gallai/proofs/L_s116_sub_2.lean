import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s116_sub_2 :
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
            ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 →
        ((q.1 - r.1) * (s.2 - r.2) - (q.2 - r.2) * (s.1 - r.1))^2 *
            ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
            ((q.1 - r.1)^2 + (q.2 - r.2)^2) := by
  -- Abstract lemma over six fresh real variables: keeps nlinarith's
  -- polynomial search space tiny so it doesn't time out.
  have lem : ∀ (A B D E al be : ℝ),
      A * D = B * (be - al) →
      al ^ 2 + B ^ 2 = D * E →
      0 < D →
      B ≠ 0 →
      (be - al) ^ 2 < al ^ 2 + B ^ 2 →
      A ^ 2 * D < B ^ 2 * E := by
    intro A B D E al be h2 h3 h4 hBne hkey
    have hB2 : 0 < B ^ 2 := sq_pos_of_ne_zero hBne
    have h2sq : (A * D) ^ 2 = (B * (be - al)) ^ 2 := by rw [h2]
    have h3B2 : B ^ 2 * (al ^ 2 + B ^ 2) = B ^ 2 * (D * E) := by rw [h3]
    have hkeyB2 : B ^ 2 * (be - al) ^ 2 < B ^ 2 * (al ^ 2 + B ^ 2) :=
      mul_lt_mul_of_pos_left hkey hB2
    nlinarith [h2sq, h3B2, hkeyB2, h4, hB2, mul_pos h4 hB2]
  intro P _ _ p _ q _ r _ _ _ s _ _ _ _ _ _ h2 h3 h4 hBne hkey
  exact lem
    ((q.1 - r.1) * (s.2 - r.2) - (q.2 - r.2) * (s.1 - r.1))
    ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))
    ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2)
    ((q.1 - r.1) ^ 2 + (q.2 - r.2) ^ 2)
    ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))
    ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))
    h2 h3 h4 hBne hkey

end Problems.sylvester_gallai
