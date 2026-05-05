import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s91_sub_2 :
    ∀ (P : Finset (ℝ × ℝ)),
      (∃ a ∈ P, ∃ b ∈ P, ∃ c ∈ P, ¬ Collinear a b c) →
      (∀ p ∈ P, ∀ q ∈ P, p ≠ q → ∃ r ∈ P, Collinear p q r ∧ r ≠ p ∧ r ≠ q) →
      ∀ p ∈ P, ∀ q ∈ P, ∀ r ∈ P, p ≠ q → ¬ Collinear p q r →
      ∀ s ∈ P, Collinear p q s → s ≠ p → s ≠ q →
      ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2)) *
          ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2)) ≥ 0 →
      ((s.1 - r.1) * (q.1 - p.1) + (s.2 - r.2) * (q.2 - p.2))^2 <
          ((q.1 - r.1) * (q.1 - p.1) + (q.2 - r.2) * (q.2 - p.2))^2 →
        ¬ Collinear r q s := by
  intro P _hex _hKelly p _hpP q _hqP r _hrP _hpq hpqr s _hsP hpqs _hsp hsq _hsame _hcase hcoll
  apply hpqr
  unfold Collinear at hpqs hcoll ⊢
  have hd : q.1 - s.1 ≠ 0 ∨ q.2 - s.2 ≠ 0 := by
    by_contra h
    push_neg at h
    apply hsq
    exact Prod.ext (by linarith [h.1]) (by linarith [h.2])
  have hprs : (p.1 - s.1) * (r.2 - s.2) = (p.2 - s.2) * (r.1 - s.1) := by
    rcases hd with hd | hd
    · have key : (q.1 - s.1) *
          ((p.1 - s.1) * (r.2 - s.2) - (p.2 - s.2) * (r.1 - s.1)) = 0 := by
        linear_combination (r.1 - s.1) * hpqs - (p.1 - s.1) * hcoll
      have h0 := (mul_eq_zero.mp key).resolve_left hd
      linarith
    · have key : (q.2 - s.2) *
          ((p.1 - s.1) * (r.2 - s.2) - (p.2 - s.2) * (r.1 - s.1)) = 0 := by
        linear_combination (r.2 - s.2) * hpqs - (p.2 - s.2) * hcoll
      have h0 := (mul_eq_zero.mp key).resolve_left hd
      linarith
  linear_combination hpqs - hcoll - hprs

end Problems.sylvester_gallai
