import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s111_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      (((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) -
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 := by
  intro P _ _ p _ q _ r _ _ _ s _ _ _ _ hsign hsqle
  set a : ℝ := (p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2) with ha_def
  set b : ℝ := (s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2) with hb_def
  have habs : |b| ≤ |a| := sq_le_sq.mp hsqle
  have hab_eq : |a| * |b| = a * b := by
    rw [← abs_mul, abs_of_nonneg hsign]
  have h_eq : (b - a) ^ 2 = (|a| - |b|) ^ 2 := by
    have hexp : (|a| - |b|) ^ 2 = |a| ^ 2 - 2 * (|a| * |b|) + |b| ^ 2 := by ring
    rw [hexp, sq_abs, sq_abs, hab_eq]
    ring
  rw [h_eq]
  have h_lo : 0 ≤ |a| - |b| := sub_nonneg.mpr habs
  have h_hi : |a| - |b| ≤ |a| := by linarith [abs_nonneg b]
  calc (|a| - |b|) ^ 2
      ≤ |a| ^ 2 := pow_le_pow_left₀ h_lo h_hi 2
    _ = a ^ 2 := sq_abs a

end Problems.sylvester_gallai
