import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s92_sub_3 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      0 < (r.1 - s.1)^2 + (r.2 - s.2)^2 := by
  intro P _hExist _hLine p _hp q _hq r _hr _hpq hnPQR s _hs hpqs _hsp _hsq _hSign _hLeq
  by_contra h
  push_neg at h
  have hsum_nonneg : 0 ≤ (r.1 - s.1)^2 + (r.2 - s.2)^2 := by positivity
  have hsum_zero : (r.1 - s.1)^2 + (r.2 - s.2)^2 = 0 := le_antisymm h hsum_nonneg
  have h1sq : (r.1 - s.1)^2 = 0 := by
    nlinarith [sq_nonneg (r.1 - s.1), sq_nonneg (r.2 - s.2)]
  have h2sq : (r.2 - s.2)^2 = 0 := by
    nlinarith [sq_nonneg (r.1 - s.1), sq_nonneg (r.2 - s.2)]
  have h1 : r.1 - s.1 = 0 := sq_eq_zero_iff.mp h1sq
  have h2 : r.2 - s.2 = 0 := sq_eq_zero_iff.mp h2sq
  have hrs : r = s := by
    apply Prod.ext
    · linarith
    · linarith
  apply hnPQR
  show Collinear p q r
  rw [hrs]
  exact hpqs

end Problems.sylvester_gallai
