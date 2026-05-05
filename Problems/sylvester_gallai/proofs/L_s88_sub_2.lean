import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s88_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 ≤
        ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 →
      ¬ Collinear p r s := by
  intro P _ _ p _ q _ r _ _ hnpqr s _ hpqs hsp _ _ _ hprs
  apply hnpqr
  unfold Collinear at hpqs hprs ⊢
  have e1 : (p.1 - s.1) *
      ((q.1 - s.1) * (r.2 - s.2) - (q.2 - s.2) * (r.1 - s.1)) = 0 := by
    linear_combination (q.1 - s.1) * hprs - (r.1 - s.1) * hpqs
  have e2 : (p.2 - s.2) *
      ((q.1 - s.1) * (r.2 - s.2) - (q.2 - s.2) * (r.1 - s.1)) = 0 := by
    linear_combination (q.2 - s.2) * hprs - (r.2 - s.2) * hpqs
  have hps : p ≠ s := fun h => hsp h.symm
  have hkey : (q.1 - s.1) * (r.2 - s.2) - (q.2 - s.2) * (r.1 - s.1) = 0 := by
    by_contra hne
    apply hps
    have h1 : p.1 - s.1 = 0 := (mul_eq_zero.mp e1).resolve_right hne
    have h2 : p.2 - s.2 = 0 := (mul_eq_zero.mp e2).resolve_right hne
    have h1' : p.1 = s.1 := by linarith
    have h2' : p.2 = s.2 := by linarith
    exact Prod.ext h1' h2'
  linear_combination hpqs - hprs + hkey

end Problems.sylvester_gallai
