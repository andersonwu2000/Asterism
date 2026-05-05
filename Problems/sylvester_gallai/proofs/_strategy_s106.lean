import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s106_sub_1
import Problems.sylvester_gallai.proofs.L_s106_sub_2
import Problems.sylvester_gallai.proofs.L_s106_sub_3
import Problems.sylvester_gallai.proofs.L_s106_sub_4

namespace Problems.sylvester_gallai

theorem s106 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      (s.1 - p.1)^2 + (s.2 - p.2)^2 < (r.1 - p.1)^2 + (r.2 - p.2)^2  := by
  intro P hwit hcov p hp q hq r hr hpq hncoll s hs hcollpqs hsp hsq hsign hsqle
  have h1 := s106_sub_1 P hwit hcov p hp q hq r hr hpq hncoll s hs hcollpqs hsp hsq hsign hsqle
  have h2 := s106_sub_2 P hwit hcov p hp q hq r hr hpq hncoll s hs hcollpqs hsp hsq hsign hsqle
  have h3 := s106_sub_3 P hwit hcov p hp q hq r hr hpq hncoll s hs hcollpqs hsp hsq hsign hsqle
  have h4 := s106_sub_4 P hwit hcov p hp q hq r hr hpq hncoll s hs hcollpqs hsp hsq hsign hsqle
  have key : ((r.1 - p.1)^2 + (r.2 - p.2)^2 - ((s.1 - p.1)^2 + (s.2 - p.2)^2))
                * ((q.1 - p.1)^2 + (q.2 - p.2)^2) > 0 := by
    nlinarith [h2, h3, h4]
  nlinarith [h1, key]

end Problems.sylvester_gallai
