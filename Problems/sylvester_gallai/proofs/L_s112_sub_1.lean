import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s112_sub_1 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 ≤
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 →
      ∃ μ : ℝ, s.1 - q.1 = μ * (p.1 - q.1) ∧ s.2 - q.2 = μ * (p.2 - q.2) := by
  intro P _ _ p _ q _ r _ hpq _ s _ hcol _ _ _ _
  unfold Collinear at hcol
  have key : (s.2 - q.2) * (p.1 - q.1) = (s.1 - q.1) * (p.2 - q.2) := by
    linear_combination -hcol
  by_cases hx : p.1 = q.1
  · have hy : p.2 ≠ q.2 := fun h => hpq (Prod.ext hx h)
    have hyne : p.2 - q.2 ≠ 0 := sub_ne_zero.mpr hy
    have hxz : p.1 - q.1 = 0 := sub_eq_zero.mpr hx
    refine ⟨(s.2 - q.2) / (p.2 - q.2), ?_, (div_mul_cancel₀ _ hyne).symm⟩
    have h0 : (s.1 - q.1) * (p.2 - q.2) = 0 := by
      rw [← key, hxz, mul_zero]
    have hs1z : s.1 - q.1 = 0 := by
      rcases mul_eq_zero.mp h0 with h | h
      · exact h
      · exact absurd h hyne
    rw [hxz, mul_zero]; exact hs1z
  · have hne : p.1 - q.1 ≠ 0 := sub_ne_zero.mpr hx
    refine ⟨(s.1 - q.1) / (p.1 - q.1), (div_mul_cancel₀ _ hne).symm, ?_⟩
    rw [div_mul_eq_mul_div, eq_div_iff hne]
    linarith [key]

end Problems.sylvester_gallai
