import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s91_sub_1
import Problems.sylvester_gallai.proofs.L_s91_sub_2
import Problems.sylvester_gallai.proofs.L_s91_sub_3

namespace Problems.sylvester_gallai

theorem s91 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 →
        ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
          ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
            ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hnc hlp p hp q hq r hr hpq hpqr s hs hpqs hsp hsq h_same h_caseB
  have h1 : r ≠ q :=
    s91_sub_1 P hnc hlp p hp q hq r hr hpq hpqr s hs hpqs hsp hsq h_same h_caseB
  have h2 : ¬ Collinear r q s :=
    s91_sub_2 P hnc hlp p hp q hq r hr hpq hpqr s hs hpqs hsp hsq h_same h_caseB
  have h3 :
      ((q.1 - r.1) * (s.2 - r.2) - (q.2 - r.2) * (s.1 - r.1))^2 /
        ((q.1 - r.1)^2 + (q.2 - r.2)^2) <
      ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
        ((q.1 - p.1)^2 + (q.2 - p.2)^2) :=
    s91_sub_3 P hnc hlp p hp q hq r hr hpq hpqr s hs hpqs hsp hsq h_same h_caseB
  exact ⟨r, hr, q, hq, s, hs, h1, h2, h3⟩

end Problems.sylvester_gallai
