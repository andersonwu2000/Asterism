import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s120_sub_1

namespace Problems.sylvester_gallai

theorem s120 :
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
        ((q.1 - p.1)^2 + (q.2 - p.2)^2) * ((q.1 - p.1)^2 + (q.2 - p.2)^2) ≤
            ((Y.1 - r.1) * (q.1 - p.1) + (Y.2 - r.2) * (q.2 - p.2))^2  := by
  intro P _hP3 _hpair p _hp q _hq r _hr _hpq _hncol s _hs _hcol _hsp _hsq hss X Y hXY hclo
  rcases hXY with ⟨hX, hY⟩ | ⟨hX, hY⟩
  · -- Case 1: hX : X = p, hY : Y = q. Eliminate X and Y, keep p and q.
    subst X
    subst Y
    have h := s120_sub_1 _ _ hss hclo
    have hring :
        (((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) -
           ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))) ^ 2 =
          ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2) *
            ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2) := by
      ring
    linarith
  · -- Case 2: hX : X = q, hY : Y = p. Eliminate X and Y, keep q and p.
    subst X
    subst Y
    have hss' :
        ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) ≥ 0 := by
      rw [mul_comm]; exact hss
    have h := s120_sub_1 _ _ hss' hclo
    have hring :
        (((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) -
           ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))) ^ 2 =
          ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2) *
            ((q.1 - p.1) ^ 2 + (q.2 - p.2) ^ 2) := by
      ring
    linarith

end Problems.sylvester_gallai
