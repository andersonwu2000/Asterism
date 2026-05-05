import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s115_sub_1
import Problems.sylvester_gallai.proofs.L_s115_sub_2
import Problems.sylvester_gallai.proofs.L_s115_sub_3

namespace Problems.sylvester_gallai

theorem s115 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ∀ (μ : ℝ),
      s.1 - q.1 = μ * (p.1 - q.1) →
      s.2 - q.2 = μ * (p.2 - q.2) →
      (q.1 - r.1)^2 + (q.2 - r.2)^2 > 0 →
      ((s.1 - r.1) * (q.2 - r.2) - (s.2 - r.2) * (q.1 - r.1))^2 *
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
          ((s.1 - r.1)^2 + (s.2 - r.2)^2)  := by
  intro P hExists hDicker p hp q hq r hr hpq hncolr s hs hcolqs hsp hsq H1 H2 μ hμ1 hμ2 hqr
  have hD2pos :=
    s115_sub_1 P hExists hDicker p hp q hq r hr hpq hncolr s hs hcolqs hsp hsq H1 H2 μ hμ1 hμ2 hqr
  have h2muA :=
    s115_sub_2 P hExists hDicker p hp q hq r hr hpq hncolr s hs hcolqs hsp hsq H1 H2 μ hμ1 hμ2 hqr
  exact s115_sub_3 P hExists hDicker p hp q hq r hr hpq hncolr s hs hcolqs hsp hsq H1 H2
    μ hμ1 hμ2 hqr hD2pos h2muA

end Problems.sylvester_gallai
