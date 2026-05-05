import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s95_sub_1
import Problems.sylvester_gallai.proofs.L_s95_sub_2
import Problems.sylvester_gallai.proofs.L_s95_sub_3

namespace Problems.sylvester_gallai

theorem s95 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      ((r.1 - p.1) * (s.2 - p.2) - (r.2 - p.2) * (s.1 - p.1))^2 /
          ((r.1 - p.1)^2 + (r.2 - p.2)^2) <
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
          ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hExists hLine p hp q hq r hr hpq hcollPQR s hs hcoll hsp hsq hSign hClose
  have h1 : (q.1 - p.1)^2 + (q.2 - p.2)^2 > 0 :=
    s95_sub_1 P hExists hLine p hp q hq r hr hpq hcollPQR s hs hcoll hsp hsq hSign hClose
  have h2 : (r.1 - p.1)^2 + (r.2 - p.2)^2 > 0 :=
    s95_sub_2 P hExists hLine p hp q hq r hr hpq hcollPQR s hs hcoll hsp hsq hSign hClose
  have h3 : ((r.1 - p.1) * (s.2 - p.2) - (r.2 - p.2) * (s.1 - p.1))^2 *
              ((q.1 - p.1)^2 + (q.2 - p.2)^2) <
            ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 *
              ((r.1 - p.1)^2 + (r.2 - p.2)^2) :=
    s95_sub_3 P hExists hLine p hp q hq r hr hpq hcollPQR s hs hcoll hsp hsq hSign hClose
  exact (div_lt_div_iff₀ h2 h1).mpr h3

end Problems.sylvester_gallai
