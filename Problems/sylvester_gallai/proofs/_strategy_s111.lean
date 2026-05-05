import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s111_sub_1

namespace Problems.sylvester_gallai

theorem s111 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      ((s.1 - p.1) * (q.1 - p.1) + (s.2 - p.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2  := by
  intro P hwit hcov p hp q hq r hr hpq hncoll s hs hcollpqs hsp hsq hsign hsqle
  have h := s111_sub_1 P hwit hcov p hp q hq r hr hpq hncoll s hs hcollpqs hsp hsq hsign hsqle
  have heq : ((s.1 - p.1) * (q.1 - p.1) + (s.2 - p.2) * (q.2 - p.2))^2 =
      (((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) -
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)))^2 := by ring
  rw [heq]
  exact h

end Problems.sylvester_gallai
