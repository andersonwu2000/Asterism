import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s113_sub_1
import Problems.sylvester_gallai.proofs.L_s113_sub_2
import Problems.sylvester_gallai.proofs.L_s113_sub_3
import Problems.sylvester_gallai.proofs.L_s113_sub_4
import Problems.sylvester_gallai.proofs.L_s113_sub_5

namespace Problems.sylvester_gallai

theorem s113 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 →
        ((q.1 - r.1) * (s.2 - r.2) - (q.2 - r.2) * (s.1 - r.1))^2 *
            ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
            ((q.1 - r.1)^2 + (q.2 - r.2)^2)  := by
  intro P hP hK p hp q hq r hr hpq hnc s hs hcs hsp hsq hside hcaseB
  have h1 := s113_sub_1 P hP hK p hp q hq r hr hpq hnc s hs hcs hsp hsq hside hcaseB
  have h2 := s113_sub_2 P hP hK p hp q hq r hr hpq hnc s hs hcs hsp hsq hside hcaseB
  have h3 := s113_sub_3 P hP hK p hp q hq r hr hpq hnc s hs hcs hsp hsq hside hcaseB
  have h4 := s113_sub_4 P hP hK p hp q hq r hr hpq hnc s hs hcs hsp hsq hside hcaseB
  exact s113_sub_5 P hP hK p hp q hq r hr hpq hnc s hs hcs hsp hsq hside hcaseB h1 h2 h3 h4

end Problems.sylvester_gallai
