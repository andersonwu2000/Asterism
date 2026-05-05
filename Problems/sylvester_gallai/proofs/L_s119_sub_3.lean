import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s119_sub_3 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        2 * (((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
              ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))) := by
  intro P _ _ p _ q _ r _ _ _ s _ _ _ _ h1 h2
  set A := (p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2) with hAdef
  set B := (s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2) with hBdef
  suffices h3 : A ^ 2 ≤ A * B by linarith
  rcases le_or_gt 0 A with hA | hA
  · rcases le_or_gt 0 B with hB | hB
    · have hAB : A ≤ B := (abs_le_of_sq_le_sq' h2 hB).2
      nlinarith [mul_nonneg hA (sub_nonneg.mpr hAB)]
    · have hAB_nonpos : A * B ≤ 0 :=
        mul_nonpos_iff.mpr (Or.inl ⟨hA, hB.le⟩)
      have hABz : A * B = 0 := le_antisymm hAB_nonpos h1
      rcases mul_eq_zero.mp hABz with hA0 | hB0
      · rw [hA0]; nlinarith
      · linarith
  · have hBnp : B ≤ 0 := by
      by_contra hpos
      push_neg at hpos
      have : A * B < 0 := mul_neg_of_neg_of_pos hA hpos
      linarith
    have hnegB : (0 : ℝ) ≤ -B := neg_nonneg.mpr hBnp
    have h2' : A ^ 2 ≤ (-B) ^ 2 := by rw [neg_sq]; exact h2
    have hBA : B ≤ A := by
      have := (abs_le_of_sq_le_sq' h2' hnegB).1
      linarith
    have hkey : -A * (A - B) ≥ 0 :=
      mul_nonneg (neg_nonneg.mpr hA.le) (sub_nonneg.mpr hBA)
    nlinarith [hkey]

end Problems.sylvester_gallai
