import Mathlib
import Problems.sylvester_gallai.Defs
import Problems.sylvester_gallai.proofs.L_s63_sub_1
import Problems.sylvester_gallai.proofs.L_s63_sub_2
import Problems.sylvester_gallai.proofs.L_s63_sub_3
import Problems.sylvester_gallai.proofs.L_s63_sub_4

namespace Problems.sylvester_gallai

theorem s63 : ∀ (p a b c : ℝ × ℝ) (t : ℝ),
    (p.1 - b.1) * (a.2 - b.2) ≠ (p.2 - b.2) * (a.1 - b.1) →
    0 < (b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2 →
    c.1 = a.1 + t * (b.1 - a.1) →
    c.2 = a.2 + t * (b.2 - a.2) →
    c ≠ a → c ≠ b →
    t ≤ 1 / 2 →
    t * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ≤
      (p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2) →
    0 ≤ t →
    ∃ x ∈ ({a, b, c} : Finset (ℝ × ℝ)),
    ∃ z ∈ ({a, b, c} : Finset (ℝ × ℝ)),
      x ≠ z ∧
      ((x.1 - z.1) ^ 2 + (x.2 - z.2) ^ 2) <
      ((p.1 - z.1) ^ 2 + (p.2 - z.2) ^ 2)  := by
  intro p a b c t h_col h_L h_c1 h_c2 h_ca _h_cb _h_half h_dot h_t
  have h_D : (p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1) ≠ 0 :=
    s63_sub_4 p a b h_col
  have h_lagrange : ((p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) ^ 2 +
      ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1)) ^ 2 :=
    s63_sub_2 p a b
  have h_dca : ((c.1 - a.1) ^ 2 + (c.2 - a.2) ^ 2) * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) =
      t ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 :=
    s63_sub_3 a b c t h_c1 h_c2
  have h_ineq : t ^ 2 * ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2) ^ 2 <
      ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2)) ^ 2 +
      ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1)) ^ 2 :=
    s63_sub_1 t ((b.1 - a.1) ^ 2 + (b.2 - a.2) ^ 2)
              ((p.1 - a.1) * (b.1 - a.1) + (p.2 - a.2) * (b.2 - a.2))
              ((p.1 - a.1) * (b.2 - a.2) - (p.2 - a.2) * (b.1 - a.1))
              h_L h_D h_t h_dot
  have h_key : (c.1 - a.1) ^ 2 + (c.2 - a.2) ^ 2 < (p.1 - a.1) ^ 2 + (p.2 - a.2) ^ 2 := by
    nlinarith [sq_nonneg (c.1 - a.1), sq_nonneg (c.2 - a.2),
               sq_nonneg (p.1 - a.1), sq_nonneg (p.2 - a.2),
               h_dca, h_lagrange, h_ineq, h_L]
  refine ⟨c, by simp, a, by simp, h_ca, ?_⟩
  exact h_key

end Problems.sylvester_gallai
