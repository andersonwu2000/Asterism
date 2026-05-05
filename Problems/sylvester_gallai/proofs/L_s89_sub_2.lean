import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s89_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((p.1 - r.1) * (q.1 - p.1) + (p.2 - r.2) * (q.2 - p.2))^2 ≤
        ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ¬ Collinear s r p := by
  intro P _ _ p _ q _ r _ _ hncol s _ hsCol hsp _ _ _ hsrp
  apply hncol
  unfold Collinear at hsCol hsrp ⊢
  by_contra h
  have hne : (p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1) ≠ 0 :=
    sub_ne_zero.mpr h
  have h1 : (s.1 - p.1) * ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) = 0 := by
    linear_combination -(p.1 - r.1) * hsCol + (q.1 - p.1) * hsrp
  have h2 : (s.2 - p.2) * ((p.1 - r.1) * (q.2 - r.2) - (p.2 - r.2) * (q.1 - r.1)) = 0 := by
    linear_combination -(p.2 - r.2) * hsCol + (q.2 - p.2) * hsrp
  have hx : s.1 - p.1 = 0 := (mul_eq_zero.mp h1).resolve_right hne
  have hy : s.2 - p.2 = 0 := (mul_eq_zero.mp h2).resolve_right hne
  exact hsp (Prod.ext (by linarith : s.1 = p.1) (by linarith : s.2 = p.2))

end Problems.sylvester_gallai
