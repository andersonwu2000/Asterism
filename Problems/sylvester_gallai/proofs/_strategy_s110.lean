import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s110_sub_1
import Problems.sylvester_gallai.proofs.L_s110_sub_2
import Problems.sylvester_gallai.proofs.L_s110_sub_3

namespace Problems.sylvester_gallai

theorem s110 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ∀ (X Y : ℝ × ℝ),
        ((X = p ∧ Y = q) ∨ (X = q ∧ Y = p)) →
        ((X.1 - r.1) * (q.1 - p.1) + (X.2 - r.2) * (q.2 - p.2))^2 ≤
            ((Y.1 - r.1) * (q.1 - p.1) + (Y.2 - r.2) * (q.2 - p.2))^2 →
        ((r.1 - Y.1) * (X.2 - Y.2) - (r.2 - Y.2) * (X.1 - Y.1))^2 /
            ((r.1 - Y.1)^2 + (r.2 - Y.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hexists hsg p hp q hq r hr hpq hncol s hs hcol hsp hsq hside X Y hdisj hcloser
  have h1 := s110_sub_1 P hexists hsg p hp q hq r hr hpq hncol s hs hcol hsp hsq hside X Y hdisj hcloser
  have h2 := s110_sub_2 P hexists hsg p hp q hq r hr hpq hncol s hs hcol hsp hsq hside X Y hdisj hcloser
  have h3 := s110_sub_3 P hexists hsg p hp q hq r hr hpq hncol s hs hcol hsp hsq hside X Y hdisj hcloser
  obtain ⟨h2a, h2b⟩ := h2
  rw [h1]
  exact div_lt_div_of_pos_left h2a h2b h3

end Problems.sylvester_gallai
