import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s114_sub_1
import Problems.sylvester_gallai.proofs.L_s114_sub_2
import Problems.sylvester_gallai.proofs.L_s114_sub_3

namespace Problems.sylvester_gallai

theorem s114 :
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
        (q.1 - p.1)^2 + (q.2 - p.2)^2 < (r.1 - Y.1)^2 + (r.2 - Y.2)^2  := by
  intro P hEx hLine p hp q hq r hr hpq hNonCol s hs hCols hsp hsq hSame X Y hXY hCloser
  have hL := s114_sub_1 P hEx hLine p hp q hq r hr hpq hNonCol s hs hCols hsp hsq hSame X Y hXY hCloser
  have h2 := s114_sub_2 P hEx hLine p hp q hq r hr hpq hNonCol s hs hCols hsp hsq hSame X Y hXY hCloser
  obtain ⟨h3a, h3b⟩ := s114_sub_3 P hEx hLine p hp q hq r hr hpq hNonCol s hs hCols hsp hsq hSame X Y hXY hCloser
  have step : ((q.1 - p.1)^2 + (q.2 - p.2)^2) * ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
      ((r.1 - Y.1)^2 + (r.2 - Y.2)^2) * ((q.1 - p.1)^2 + (q.2 - p.2)^2) := by
    rw [hL]; linarith
  exact lt_of_mul_lt_mul_right step h3a.le

end Problems.sylvester_gallai
