import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s90_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
        ¬ Collinear r s q := by
  intro P _ _ p _ q _ r _ _ hcoll s _ hcolls _ hsq _ _ hrsq
  apply hcoll
  show (p.1 - r.1) * (q.2 - r.2) = (p.2 - r.2) * (q.1 - r.1)
  have hcolls' : (p.1 - s.1) * (q.2 - s.2) = (p.2 - s.2) * (q.1 - s.1) := hcolls
  have hrsq' : (r.1 - q.1) * (s.2 - q.2) = (r.2 - q.2) * (s.1 - q.1) := hrsq
  have hsq_or : s.1 ≠ q.1 ∨ s.2 ≠ q.2 := by
    by_contra h
    push_neg at h
    exact hsq (Prod.ext h.1 h.2)
  rcases hsq_or with hs1 | hs2
  · have h1 : s.1 - q.1 ≠ 0 := sub_ne_zero.mpr hs1
    have key : (s.1 - q.1) * ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) = 0 := by
      linear_combination (p.1 - q.1) * hrsq' + (r.1 - q.1) * hcolls'
    have hzero : (p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1) = 0 :=
      (mul_eq_zero.mp key).resolve_left h1
    linarith
  · have h2 : s.2 - q.2 ≠ 0 := sub_ne_zero.mpr hs2
    have key : (s.2 - q.2) * ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) = 0 := by
      linear_combination (p.2 - q.2) * hrsq' + (r.2 - q.2) * hcolls'
    have hzero : (p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1) = 0 :=
      (mul_eq_zero.mp key).resolve_left h2
    linarith

end Problems.sylvester_gallai
