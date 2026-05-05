import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s114_sub_3 :
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
        0 < (q.1 - p.1)^2 + (q.2 - p.2)^2 ∧
        0 < ((r.1 - Y.1) * (q.2 - p.2) - (r.2 - Y.2) * (q.1 - p.1))^2 := by
  intro P _hABC _hLine p _hp q _hq r _hr hpq hpqr s _hs _hpqs _hsp _hsq _hSS X Y hXY _hClose
  have hD : (p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1) ≠ 0 := by
    intro heq
    apply hpqr
    unfold Collinear
    linarith
  have hpqne : 0 < (q.1 - p.1)^2 + (q.2 - p.2)^2 := by
    rcases eq_or_ne (q.1 - p.1) 0 with h1 | h1
    · have h2 : q.2 - p.2 ≠ 0 := by
        intro h2
        apply hpq
        have e1 : p.1 = q.1 := by linarith
        have e2 : p.2 = q.2 := by linarith
        exact Prod.ext e1 e2
      have hp2 : 0 < (q.2 - p.2)^2 := sq_pos_of_ne_zero h2
      have hp1 : 0 ≤ (q.1 - p.1)^2 := sq_nonneg _
      linarith
    · have hp1 : 0 < (q.1 - p.1)^2 := sq_pos_of_ne_zero h1
      have hp2 : 0 ≤ (q.2 - p.2)^2 := sq_nonneg _
      linarith
  refine ⟨hpqne, ?_⟩
  rcases hXY with ⟨_, hYq⟩ | ⟨_, hYp⟩
  · rw [hYq]
    have hcross_ne :
        (r.1 - q.1) * (q.2 - p.2) - (r.2 - q.2) * (q.1 - p.1) ≠ 0 := by
      intro h
      apply hD
      have hring :
          (p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1) =
            -((r.1 - q.1) * (q.2 - p.2) - (r.2 - q.2) * (q.1 - p.1)) := by ring
      linarith
    exact sq_pos_of_ne_zero hcross_ne
  · rw [hYp]
    have hcross_ne :
        (r.1 - p.1) * (q.2 - p.2) - (r.2 - p.2) * (q.1 - p.1) ≠ 0 := by
      intro h
      apply hD
      have hring :
          (p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1) =
            -((r.1 - p.1) * (q.2 - p.2) - (r.2 - p.2) * (q.1 - p.1)) := by ring
      linarith
    exact sq_pos_of_ne_zero hcross_ne

end Problems.sylvester_gallai
