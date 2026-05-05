import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s117_sub_1
import Problems.sylvester_gallai.proofs.L_s117_sub_2
import Problems.sylvester_gallai.proofs.L_s117_sub_3

namespace Problems.sylvester_gallai

theorem s117 :
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
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
          ((r.1 - s.1)^2 + (r.2 - s.2)^2)  := by
  intro P hNonCol hSG p hp q hq r hr hpq hpqr s hs hpqs hsp hsq hSame hSqLe
  have h1 :
      ((r.1 - s.1) * (p.2 - s.2) - (r.2 - s.2) * (p.1 - s.1))^2 *
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) =
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
          ((s.1 - p.1)^2 + (s.2 - p.2)^2) :=
    s117_sub_1 P hNonCol hSG p hp q hq r hr hpq hpqr s hs hpqs hsp hsq hSame hSqLe
  have h2 :
      (s.1 - p.1)^2 + (s.2 - p.2)^2 < (r.1 - s.1)^2 + (r.2 - s.2)^2 :=
    s117_sub_2 P hNonCol hSG p hp q hq r hr hpq hpqr s hs hpqs hsp hsq hSame hSqLe
  have h3 :
      0 < ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 :=
    s117_sub_3 P hNonCol hSG p hp q hq r hr hpq hpqr s hs hpqs hsp hsq hSame hSqLe
  have h4 := mul_lt_mul_of_pos_left h2 h3
  linarith [h1, h4]

end Problems.sylvester_gallai
