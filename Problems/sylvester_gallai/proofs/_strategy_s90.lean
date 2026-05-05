import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s90_sub_1
import Problems.sylvester_gallai.proofs.L_s90_sub_2
import Problems.sylvester_gallai.proofs.L_s90_sub_3

namespace Problems.sylvester_gallai

theorem s90 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
        ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
          ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
            ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hex hcond p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hside hcase
  have h1 : r ≠ s :=
    s90_sub_1 P hex hcond p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hside hcase
  have h2 : ¬ Collinear r s q :=
    s90_sub_2 P hex hcond p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hside hcase
  have h3 :
      ((s.1 - r.1) * (q.2 - r.2) - (s.2 - r.2) * (q.1 - r.1))^2 /
          ((s.1 - r.1)^2 + (s.2 - r.2)^2) <
        ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
          ((q.1 - p.1)^2 + (q.2 - p.2)^2) :=
    s90_sub_3 P hex hcond p hp q hq r hr hpq hncoll s hs hcoll hsp hsq hside hcase
  exact ⟨r, hr, s, hs, q, hq, h1, h2, h3⟩

end Problems.sylvester_gallai
