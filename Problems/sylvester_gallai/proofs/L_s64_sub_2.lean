import Mathlib
import Problems.sylvester_gallai.Defs

namespace Problems.sylvester_gallai

-- entry_kind: Builder
theorem s64_sub_2 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    t ≤ 1 / 2 →
    t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ≤
      (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) →
    t < 0 →
    (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) < 0 →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2) := by
  intro p a b c t hncol hL hc1 hc2 hca hcb ht2 hdot_ge ht_neg hdot_neg
  -- Witnesses: x = a, z = b
  refine ⟨a, by simp, b, by simp, ?_, ?_⟩
  · -- a ≠ b: a = b makes L = 0, contradicting hL > 0
    intro hab
    rw [hab] at hL
    simp at hL
  · -- Goal: (a.1-b.1)²+(a.2-b.2)² < (p.1-b.1)²+(p.2-b.2)²
    -- Note (a.1-b.1)²+(a.2-b.2)² = L = (b.1-a.1)²+(b.2-a.2)²
    have hL_sym : (a.1 - b.1) ^ 2 + (a.2 - b.2) ^ 2 =
        (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 := by ring
    -- Db ≠ 0 (hncol says the two cross terms are unequal)
    have hDb_ne : (p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1) ≠ 0 := fun h =>
      hncol (by linarith)
    -- Db² > 0
    have hDb_pos : 0 < ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 :=
      sq_pos_of_ne_zero hDb_ne
    -- Lagrange identity: L · |p-b|² = (dot - L)² + Db²  (by ring)
    have lagrange :
        ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) * ((p.1 - b.1) ^ 2 + (p.2 - b.2) ^ 2) =
        ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
          ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 +
        ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1)) ^ 2 := by ring
    -- dot < 0 and L > 0, so dot * (2L - dot) < 0 (neg * pos)
    -- Equivalently: (dot-L)² - L² = -(dot*(2L-dot)) > 0
    have hprod :
        ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) *
        (2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) -
          (p.1 - a.1) * (b.1 - a.1) - (p.2 - a.2) * (b.2 - a.2)) < 0 :=
      mul_neg_of_neg_of_pos hdot_neg (by linarith)
    -- (dot - L)² > L²
    have hdot_sq :
        ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 <
        ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) -
          ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)) ^ 2 := by nlinarith [hprod]
    -- L · |p-b|² = (dot-L)² + Db² > L² + 0 = L²
    have h_LB_gt :
        ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 <
        ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) * ((p.1 - b.1) ^ 2 + (p.2 - b.2) ^ 2) := by
      linarith [lagrange, hdot_sq, sq_nonneg ((p.1 - b.1) * (a.2 - b.2) - (p.2 - b.2) * (a.1 - b.1))]
    -- Since L > 0: |p-b|² > L = |a-b|²
    rw [hL_sym]
    nlinarith [h_LB_gt, hL]

end Problems.sylvester_gallai
