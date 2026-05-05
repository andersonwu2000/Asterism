import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s108_sub_1 :
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
        Y ∈ P ∧ X ∈ P ∧ Y ≠ r ∧ ¬ Collinear Y r X := by
  intro P _ _ p hp q hq r _ _ hncoll s _ _ _ _ _ X Y hxy _
  rcases hxy with ⟨hX, hY⟩ | ⟨hX, hY⟩
  · refine ⟨?_, ?_, ?_, ?_⟩
    · rw [hY]; exact hq
    · rw [hX]; exact hp
    · rw [hY]
      intro hqr
      apply hncoll
      show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
      rw [hqr]; ring
    · rw [hY, hX]
      intro hcoll
      apply hncoll
      have h : (q.1 - p.1) * (r.2 - p.2) = (q.2 - p.2) * (r.1 - p.1) := hcoll
      show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
      linear_combination h
  · refine ⟨?_, ?_, ?_, ?_⟩
    · rw [hY]; exact hp
    · rw [hX]; exact hq
    · rw [hY]
      intro hpr
      apply hncoll
      show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
      rw [hpr]; ring
    · rw [hY, hX]
      intro hcoll
      apply hncoll
      have h : (p.1 - q.1) * (r.2 - q.2) = (p.2 - q.2) * (r.1 - q.1) := hcoll
      show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
      linear_combination -h

end Problems.sylvester_gallai
