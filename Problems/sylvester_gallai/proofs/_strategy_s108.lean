import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s108_sub_1
import Problems.sylvester_gallai.proofs.L_s108_sub_2

namespace Problems.sylvester_gallai

theorem s108 :
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
        ∃ p' ∈ P, ∃ q' ∈ P, ∃ r' ∈ P, p' ≠ q' ∧ ¬ Collinear p' q' r' ∧
          ((q'.1 - p'.1) * (r'.2 - p'.2) - (q'.2 - p'.2) * (r'.1 - p'.1))^2 /
            ((q'.1 - p'.1)^2 + (q'.2 - p'.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2)  := by
  intro P hex hLLP p hp q hq r hr hpq hncoll s hs hcol_pqs hsp hsq hsame X Y hdisj hXY
  have h1 : Y ∈ P ∧ X ∈ P ∧ Y ≠ r ∧ ¬ Collinear Y r X :=
    s108_sub_1 P hex hLLP p hp q hq r hr hpq hncoll s hs hcol_pqs hsp hsq hsame X Y hdisj hXY
  have h2 :
      ((r.1 - Y.1) * (X.2 - Y.2) - (r.2 - Y.2) * (X.1 - Y.1))^2 /
            ((r.1 - Y.1)^2 + (r.2 - Y.2)^2) <
          ((q.1 - p.1) * (r.2 - p.2) - (q.2 - p.2) * (r.1 - p.1))^2 /
            ((q.1 - p.1)^2 + (q.2 - p.2)^2) :=
    s108_sub_2 P hex hLLP p hp q hq r hr hpq hncoll s hs hcol_pqs hsp hsq hsame X Y hdisj hXY
  obtain ⟨hY_mem, hX_mem, hYr, hncoll'⟩ := h1
  exact ⟨Y, hY_mem, r, hr, X, hX_mem, hYr, hncoll', h2⟩

end Problems.sylvester_gallai
