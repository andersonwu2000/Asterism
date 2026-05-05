import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s102_sub_1
import Problems.sylvester_gallai.proofs.L_s102_sub_2
import Problems.sylvester_gallai.proofs.L_s102_sub_3

namespace Problems.sylvester_gallai

theorem s102 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 →
        ((q.1 - r.1) * (s.2 - r.2) - (q.2 - r.2) * (s.1 - r.1))^2 /
          ((q.1 - r.1)^2 + (q.2 - r.2)^2) <
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
          ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hex hKelly p hp q hq r hr hpq hncol s hs hcol hsp hsq hdot hcase
  have h1 : (q.1 - p.1)^2 + (q.2 - p.2)^2 > 0 :=
    s102_sub_1 P hex hKelly p hp q hq r hr hpq hncol s hs hcol hsp hsq hdot hcase
  have h2 : (q.1 - r.1)^2 + (q.2 - r.2)^2 > 0 :=
    s102_sub_2 P hex hKelly p hp q hq r hr hpq hncol s hs hcol hsp hsq hdot hcase
  have h3 : ((q.1 - r.1) * (s.2 - r.2) - (q.2 - r.2) * (s.1 - r.1))^2 *
              ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
            ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
              ((q.1 - r.1)^2 + (q.2 - r.2)^2) :=
    s102_sub_3 P hex hKelly p hp q hq r hr hpq hncol s hs hcol hsp hsq hdot hcase
  rw [div_lt_div_iff₀ h2 h1]
  exact h3

end Problems.sylvester_gallai
