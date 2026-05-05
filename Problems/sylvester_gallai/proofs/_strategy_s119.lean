import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s119_sub_1
import Problems.sylvester_gallai.proofs.L_s119_sub_2
import Problems.sylvester_gallai.proofs.L_s119_sub_3
import Problems.sylvester_gallai.proofs.L_s119_sub_4

namespace Problems.sylvester_gallai

theorem s119 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      (s.1 - p.1)^2 + (s.2 - p.2)^2 < (r.1 - s.1)^2 + (r.2 - s.2)^2  := by
  intro P hexNonCol hLine p hp q hq r hr hpq hnpqr s hs hCols hsp hsq hdotNN hdotSq
  have h1 := s119_sub_1 P hexNonCol hLine p hp q hq r hr hpq hnpqr s hs hCols hsp hsq hdotNN hdotSq
  have h2 := s119_sub_2 P hexNonCol hLine p hp q hq r hr hpq hnpqr s hs hCols hsp hsq hdotNN hdotSq
  have h3 := s119_sub_3 P hexNonCol hLine p hp q hq r hr hpq hnpqr s hs hCols hsp hsq hdotNN hdotSq
  have h4 := s119_sub_4 P hexNonCol hLine p hp q hq r hr hpq hnpqr s hs hCols hsp hsq hdotNN hdotSq
  have hAC : 0 < ((r.1 - s.1)^2 + (r.2 - s.2)^2 - ((s.1 - p.1)^2 + (s.2 - p.2)^2)) *
                  ((q.1 - p.1)^2 + (q.2 - p.2)^2) := by linarith
  have hA : 0 < (r.1 - s.1)^2 + (r.2 - s.2)^2 - ((s.1 - p.1)^2 + (s.2 - p.2)^2) :=
    pos_of_mul_pos_left hAC h4.le
  linarith

end Problems.sylvester_gallai
