import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s87_sub_1
import Problems.sylvester_gallai.proofs.L_s87_sub_2

namespace Problems.sylvester_gallai

theorem s87 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
        ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
          ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
            ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hNonCol hLine p hp q hq r hr hpq hnc s hs hcs hsp hsq hside
  by_cases hcase :
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2
  · exact s87_sub_1 P hNonCol hLine p hp q hq r hr hpq hnc s hs hcs hsp hsq hside hcase
  · push_neg at hcase
    exact s87_sub_2 P hNonCol hLine p hp q hq r hr hpq hnc s hs hcs hsp hsq hside
      (le_of_lt hcase)

end Problems.sylvester_gallai
