import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s92_sub_1
import Problems.sylvester_gallai.proofs.L_s92_sub_2
import Problems.sylvester_gallai.proofs.L_s92_sub_3

namespace Problems.sylvester_gallai

theorem s92 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ((r.1 - s.1) * (p.2 - s.2) - (r.2 - s.2) * (p.1 - s.1))^2 /
          ((r.1 - s.1)^2 + (r.2 - s.2)^2) <
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
          ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hex hreg p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hsign hpcloser
  have h1 :=
    s92_sub_1 P hex hreg p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hsign hpcloser
  have hu :=
    s92_sub_2 P hex hreg p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hsign hpcloser
  have hrs :=
    s92_sub_3 P hex hreg p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hsign hpcloser
  exact (div_lt_div_iff₀ hrs hu).mpr h1

end Problems.sylvester_gallai
